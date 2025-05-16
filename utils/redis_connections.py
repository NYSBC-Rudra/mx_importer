#Redis nyx-container gui connector
import os
import redis
import json
from typing import Dict, Any

class RedisConnection:
    def __init__(self, client=None, beamline_id='Nyx', host=None, owner=None, port=None, main_container='NyxDewar'):
        if not client:
            self.redishost = os.environ.get("REDIS_HOST", "localhost")
            self.redisport = os.environ.get("REDIS_PORT", "6379")
            client = redis.Redis(host = self.redishost, port = self.redisport, db =1, decode_responses=True)
        self.client = client
        self.pubsub = self.client.pubsub()
        self.beamline_id = beamline_id
        self.owner = owner
        self.main_container = main_container
        self.main_container_capacity = self.get(f"{self.main_container}:capacity")
        self.container = {}
        self.container['pucks'] = set()
        if not self.main_container_capacity:
            self.createRedisContainer(capacity=29, name=self.main_container)
        else:
            self.fill_container()
            self.main_container_capacity = int(self.main_container_capacity)
        
        print(f"Redis connection established\n current container: {self.container}")

    
    '''
    fills the Container object with the current state of the redis container
    '''
    def fill_container(self):
        for i in range(1, int(self.main_container_capacity)+1):
            self.container[i] = self.get(f"{self.main_container}:{i}")
        self.container['capacity'] = self.get(f"{self.main_container}:capacity")
        self.container['pucks'] = self.client.smembers(f"{self.main_container}:pucks")


    '''
    Creates an empty redis container (full Dewar) with given capacity.
    makes following redis keys:
    {name}:capacity
    {name}:pucks
    {name}:1 ... {name}:x
    '''
    def createRedisContainer(self, capacity: int, name: str = 'NyxDewar', **kwargs):
        self.container = {f'{name}:capacity': capacity}
        for i in range(1, capacity+1):
            self.container[i] = 'empty'
            self.client.set(f"{name}:{i}", json.dumps("empty"))
        self.client.set(f'{name}:capacity', json.dumps(capacity))
        self.main_container_capacity = capacity
        #empty pucks from new container
        self.client.delete(f"{name}:pucks")


    '''
    creates an empty puck with the given capacity
    makes no redis keys
    will make values to be easily added to redis when adding puck to the main container
    '''
    def createPuck(self, name: str, capacity: int = 16):
        newpuck = {'name': name, 'pins': [], 'proposal_number':999999}
        for i in range(1, capacity+1):
            newpuck[i] = ''
        newpuck['bitmap']= [0] * capacity
        return newpuck
    

    '''
    creates redis keys for puck
    {dewarname}:{puckname}:locations -> bitmap of puck 
    {dewarname}:{puckname}:pins -> list of pins
    {dewarname}:{puckname}:proposal -> proposal number
    {dewarname}:{puckname}:1 ... {dewarname}:{puckname}:x -> list of samples as hashsets
    '''
    def addPuckToMain(self, puck, position: int):

        #check if puck is empty and delete all values
        if self.container[position] != 'empty':
            delete_puck = f"{self.main_container}:{self.container[position]}*"
            self.client.delete(*self.client.keys(delete_puck))
        puckname = puck['name']
        proposalnum = puck['proposal_number']
        size = len(puck['pins'])
        bitmap = puck['bitmap']
        pins = puck['pins']
        self.container['pucks'].add(puckname)
        self.container[position] = puckname
        self.client.set(f"{self.main_container}:{position}", json.dumps(puckname))
        self.client.publish(f"{self.main_container}:{position}:pub", json.dumps(puckname))
        #adding puck to container pucklist
        self.client.sadd(f"{self.main_container}:pucks", json.dumps(puckname))
        #setting everything about puck (for info purposes)
        self.client.set(f"{self.main_container}:{puckname}", json.dumps(f'All keys for puck:\npins, proposal_number, bitmap, 1...{size}'))
        #setting puck proposal number
        self.client.set(f"{self.main_container}:{puckname}:proposal_number", json.dumps(proposalnum))
        #setting puck bitmap and pins
        pin_count = 1
        for bit in bitmap:
            #setting bitmap
            self.client.setbit(f'{self.main_container}:{puckname}:bitmap', pin_count, bit)
            if bit == 1:
                #if pins are present add to redis
                pinname = puck[pin_count]['name']
                self.client.sadd(f'{self.main_container}:{puckname}:pins', json.dumps(pinname))
                self.client.set(f'{self.main_container}:{puckname}:{pin_count}', json.dumps(pinname))
                self.client.hset(f'{self.main_container}:{puckname}:{pinname}', mapping=puck[pin_count])
            pin_count += 1

    def removePuckFromMain(self, position: int):
        if self.container[position] != 'empty':
            puck_name = self.container[position]
            print(f"Removing puck {puck_name} from position {position}.")
            delete_puck = f"{self.main_container}:{self.container[position]}*"
            print(delete_puck)
            self.client.delete(*self.client.keys(delete_puck))
            self.client.srem(f"{self.main_container}:pucks", json.dumps(self.container[position]))
            self.client.set(f"{self.main_container}:{position}", json.dumps('empty'))
            self.client.publish(f"{self.main_container}:{position}:pub", json.dumps('empty'))
            try:
                self.container['pucks'].remove(self.container[position])
            except Exception as e:
                print(e)
            self.container[position] = 'empty'


    def addSampleTopuck(self, sample, puck, position: int):
        if puck['bitmap'][position-1] == 1:
            puck['pins'].remove(puck[position]['name'])
        puck['pins'].append(sample['name'])
        puck['bitmap'][position-1] = 1
        if puck['proposal_number'] != 999999:
            sample['proposal_number'] = puck['proposal_number']
        sample['puck_name'] = puck['name']
        sample['puck_position'] = position
        puck[position] = sample
        return puck


    def createSample(self, sample_name: str, sample_data: Dict[str, Any] = {}):
        newsample = {}
        if sample_data:
            keys = [
                'folder', 'deltaphi', 'exposure', 'totalphi', 'transmission',
                'targetresolution', 'beamsize', 'priority', 'collectiontype',
                'model', 'spacegroup', 'cellparameters', 'proposal_number'
            ]
            
            newsample = {key: sample_data.get(key, None) for key in keys}
        newsample['name'] = sample_name
        return newsample

    def get(self, key):
        """
        Retrieves a value from Redis and attempts to decode it from JSON.

        Args:
            key (str): The Redis key to retrieve.

        Returns:
            The decoded value (if JSON) or the raw value.
        """
        try:
            value = self.client.get(key)
            if value is not None:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
        except Exception as e:
            print(f"Failed to get value for key '{key}': {e}")
            return None




    
        





class RedisGetter:
    def __init__(self, client=None, beamline_id='nyx', host=None, owner=None, port=None, main_container='NyxDewar'):
        if not client:
            self.redishost = os.environ.get("REDIS_HOST", "localhost")
            self.redisport = os.environ.get("REDIS_PORT", "6379")
            client = redis.Redis(host = self.redishost, port = self.redisport, db =1, decode_responses=True)
        self.client = client
        self.beamline_id = beamline_id
        self.maincontainer = main_container


    def getContainerCapacity(self):
        try:
            return int(self.get(f"{self.maincontainer}:capacity"))
        except Exception as e:
            print(f"Error getting container capacity: {e}")
            return None
    
    def getContainerPucks(self):
        try:
            pucks = self.client.smembers(f"{self.maincontainer}:pucks")
            if pucks:
                a = set([json.loads(puck) for puck in pucks])
                return a
            else:
                print(f"No pucks found in container {self.maincontainer}.")
                return []
        except Exception as e:
            print(f"Error getting container pucks: {e}")
            return []

    def getPuckNamefromPosition(self, position: int):
        try:
            puck_name = self.get(f"{self.maincontainer}:{position}")
            if puck_name:
                return puck_name
            else:
                print(f"Puck in {position} not found.")
                return None
        except Exception as e:
            print(f"Error getting puck info: {e}")
            return None

    def getPuckPins(self, puck_name: str):
        try:
            pins = self.client.smembers(f"{self.maincontainer}:{puck_name}:pins")
            if pins:
                a = set([json.loads(pin) for pin in pins])
                return a
            else:
                print(f"No pins found in puck {self.maincontainer}:{puck_name}.")
                return []
        except Exception as e:
            print(f"Error getting puck pins: {e}")
            return None

    def getPuckBitmap(self, puck_name: str):
        try:
            bitmap_key = f"{self.maincontainer}:{puck_name}:bitmap"
            bitmap_length = self.client.strlen(bitmap_key) * 8
            return [self.client.getbit(bitmap_key, i) for i in range(1, bitmap_length + 1)]
        except Exception as e:
            print(f"Error getting puck bitmap: {e}")
            return None
        
    def getPuckProposal(self, puck_name: str):
        try:
            proposal_key = f"{self.maincontainer}:{puck_name}:proposal_number"
            return int(self.get(proposal_key))
        except Exception as e:
            print(f"Error getting puck proposal: {e}")
            return None

    def getSampleNameFromPuck(self, puck_name: str, position: int):
        try:
            sample_key = f"{self.maincontainer}:{puck_name}:{position}"
            sample = self.get(sample_key)
            if sample:
                return sample
            else:
                print(f"No sample found at position {position} in puck {puck_name}.")
                return None
        except Exception as e:
            print(f"Error getting sample from puck: {e}")
            return None
        
    def getSampleData(self, puckname, samplename, datakey:str):
        try:
            get_key = f'{self.maincontainer}:{puckname}:{samplename}'
            data = self.client.hget(get_key, datakey)
            if data:
                return data
            else:
                print(f"No data found for {datakey} in sample {samplename}.")
                return None
        except Exception as e:
            print(f"Error getting sample data: {e}")
            return None
    
    def getPuckBitmap(self, puckname):
        number_of_pins = len(self.getPuckPins(puckname))
        bitmap = []
        current_position = 1
        while sum(bitmap) < number_of_pins:
            bit = self.client.getbit(f"{self.maincontainer}:{puckname}:bitmap", current_position)
            bitmap.append(bit)
            current_position += 1
        return bitmap

        
    def get(self, key):
        """
        Retrieves a value from Redis and attempts to decode it from JSON.

        Args:
            key (str): The Redis key to retrieve.

        Returns:
            The decoded value (if JSON) or the raw value.
        """
        try:
            value = self.client.get(key)
            if value is not None:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
        except Exception as e:
            print(f"Failed to get value for key '{key}': {e}")
            return None
    

