import os
from typing import Dict, Any
import time
import getpass
import redis

class DBConnection:
    def __init__(self, beamline_id="nyx", host=None, owner=None):
        if not host:
            main_server = os.environ.get("MONGODB_HOST", "localhost")
        else:
            main_server = host

        services_config = {
            "amostra": {"host": main_server, "port": "7770"},
            "conftrak": {"host": main_server, "port": "7771"},
            "metadataservice": {"host": main_server, "port": "7772"},
            "analysisstore": {"host": main_server, "port": "7773"},
        }
        # self.sample_ref = acc.SampleReference(**services_config["amostra"])
        # self.container_ref = acc.ContainerReference(**services_config["amostra"])
        # self.request_ref = acc.RequestReference(**services_config["amostra"])

        # self.configuration_ref = ccc.ConfigurationReference(
        #     **services_config["conftrak"]
        # )
        self.client = redis.Redis(host="10.67.147.227", port=3900, db=0)
        self.beamline_id = beamline_id
        if owner is not None:
            self.owner = getpass.getuser()
        else:
            self.owner = owner

    def getContainer(self, filter=None):
        container = {}
        if filter:
            containers = list(self.container_ref.find(**filter))
            if containers:
                container = max(containers, key=lambda x: x.get('modified_time', float('-inf')))
            else:
                container = {}
        return container

    def createContainer(self, name: str, capacity: int, kind: str, **kwargs):
        if capacity is not None:
            kwargs["content"] = [""] * capacity
        #uid = self.container_ref.create(
        #    name=name, owner=self.owner, kind=kind, modified_time=time.time(), **kwargs
        #)
        newpuck = {1: '', 2: '', 3: '', 4: '', 5: '', 6: '', 7: '', 8: '', 9: '', 10: '', 11: '', 12: '', 13: '', 14: '', 15: '', 16: '', 'name':name, 'kind':kind}
        return newpuck

    def getOrCreateContainerID(self, name: str, capacity: int, kind: str, **kwargs):
        container = self.getContainer(
            filter={"name": name, "kind": kind, "owner": self.owner}
        )
        if not container:
            container_id = self.createContainer(name, capacity, kind, **kwargs)
        else:
            container_id = container["uid"]
        return container_id

    def updateContainer(
        self, container: Dict[str, Any]
    ):  # really updating the contents
        cont = container["uid"]
        q = {"uid": container.pop("uid", "")}
        container.pop("time", "")
        self.container_ref.update(
            q, {"content": container["content"], "modified_time": time.time()}
        )

        return cont

    def emptyContainer(self, id):
        c = self.getContainer(filter={"uid": id})
        if c is not None:
            c["content"] = [""] * len(c["content"])
            self.updateContainer(c)
            return True
        return False

    def insertIntoContainer(self, parent_uid, position, child_uid):
        # dewar = self.getContainer(filter={'owner':self.owner, 'name': dewar_name})
        # puck = self.getContainer(filter={'owner':self.owner, 'kind': '16_pin_puck', 'name': puck_name})
        parent_container = self.getContainer(filter={"uid": parent_uid})
        if parent_container:
            parent_container["content"][position] = child_uid
            self.updateContainer(parent_container)
            return True
        return False

    def removeFromContainer(self, parent_uid, position, child_uid):
        parent_container = self.getContainer(filter={"uid": parent_uid})
        if parent_container:
            if parent_container["content"][position] == child_uid:
                parent_container["content"][position] = ""
                self.updateContainer(parent_container)
                return True
        return False

    def getAllPucks(self):
        filters = {"kind": "16_pin_puck", "owner": self.owner}
        return list(self.container_ref.find(**filters))

    def getBLConfig(self, paramName):
        return self.beamlineInfo(paramName).get("val", None)

    def beamlineInfo(self, info_name) -> Dict[str, Any]:
        """
        to fetch info:  info = beamlineInfo('x25', 'det')
        """

        # if it exists it's a query or update
        try:
            bli = list(
                self.configuration_ref.find(
                    key="beamline_info",
                    beamline_id=self.beamline_id,
                    info_name=info_name,
                )
            )[0]
            return bli['info']

        # else it's a create
        except conftrak.exceptions.ConfTrakNotFoundException:
            return {}

    @property
    def primary_dewar_name(self):
        return self.getBLConfig("primaryDewarName")

    @property
    def primary_dewar_uid(self):
        return self.getContainer(filter={"name": self.primary_dewar_name, "owner": self.beamline_id.lower()})['uid']

    def getSample(self, filter):
        samples = list(self.sample_ref.find(**filter))
        if samples:
            return samples[0]
        return {}

    def createSample(self, sample_name, kind="pin", proposalID=None, container=None, **kwargs):
        if "request_count" not in kwargs:
            kwargs["request_count"] = 0
        
        #return self.sample_ref.create(
        #    name=sample_name,
        #    owner=self.owner,
        #    kind=kind,
        #    proposalID=proposalID,
        #    **kwargs
        #)
        sampledict = {'name':sample_name, 'kind':kind, 'proposalID':proposalID, 'puck_name':container}
        return sampledict
