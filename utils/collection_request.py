#!/usr/bin/env python
"""
Created on 21-Jan-2025
by jwojdyla
"""

# Python libs
import os
import math
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal

# In-house code


class CollectionRequest(BaseModel):
    beam_size: str = Field(..., description="Beam size used during data collection.")
    data_directory_name: str = Field(..., description="Path to the directory where data will be stored.")
    collection_type: Literal["dataset", "screenshots", "raster", "vector"] = Field(
        ..., description="Type of data collection (allowed values: dataset, screenshots, raster, vector).")
    detector_distance_mm: float = Field(..., description="Distance to the detector in millimeters.")
    energy: float = Field(..., ge=5000.0, le=20000.0, description="Energy in eV (range: 5000-20000 eV).")
    exposure_per_image: float = Field(..., ge=0.01, le=5.0, description="Exposure time per image in seconds.")
    filename: str = Field(..., description="User spreadsheet file prefix for the data file.")
    img_width: float = Field(..., ge=0.0, le=5.0, description="Image width in degrees.")
    omega_start: float = Field(..., ge=0.0, le=360.0, description="Starting omega angle in degrees.")
    pin: str = Field(..., description="Pin position in puck, padded to two digits.")
    puck: str = Field(..., description="Puck name, extracted from user spreadsheet.")
    resolution: float = Field(..., description="Resolution in angstroms. Calculated from dtz")
    scan_range: float = Field(..., ge=0.1, le=360.0, description="Total scan range in degrees.")
    screening: Literal["7x45", "2x90", "4x90", "3x30"] = Field(...,
        description="Defines screening collection. Available values are ['7x45', '2x90', '4x90', '3x30'].")
    transmission: float = Field(..., ge=1.0, le=100.0, description="Transmission percentage.")
    wavelength: float = Field(..., ge=0.5, le=2.5, description="Wavelength in angstroms.")

    @model_validator(mode="before")
    def check_non_empty_fields(cls, values):
        """
        Ensure that all fields are non-empty.
        """
        for field_name, field_value in values.items():
            if field_value is None or field_value == '':
                raise ValueError(f"Field '{field_name}' cannot be empty.")
        return values

    @field_validator("beam_size")
    def validate_beam_size(cls, value):
        """
        Validate that the beam size is in the list of available apertures.
        """
        # FOR Current NYX GUI CODE as of 2025-05-06
        available_diameters = ["10", "20", "30", "50", "100"]

        if value not in available_diameters:
            raise ValueError(f"Invalid beam size '{value}'. Must be one of: {', '.join(available_diameters)}.")
        return value

    @field_validator("data_directory_name")
    def validate_data_directory(cls, value):
        """
        Validate the data directory path.
        """
        if not os.path.isabs(value):
            raise ValueError("Data directory path must be absolute.")
        if not os.path.exists(value):
            try:
                os.makedirs(value)
            except OSError as e:
                raise ValueError(f"Failed to create data directory '{value}': {e}")
        return value

    @field_validator("detector_distance_mm")
    def validate_detector_distance_mm(cls, value):
        """
        Validate the detector distance based on the bounds defined in the DetectorDistance object.
        """
        # FOR Current NYX GUI CODE as of 2025-05-06
        min_val, max_val = [140,600]
        if not (min_val <= value <= max_val):
            raise ValueError(f"Detector distance must be between {min_val:.3f} mm and {max_val:.3f} mm.")
        return value

    @field_validator("energy")
    def validate_energy(cls, value):
        """Ensure energy is 12670 eV."""
        if value != 12670:
            raise ValueError("Energy must be 12670 eV.")
        return value

    @field_validator("wavelength")
    def validate_wavelength(cls, value):
        """Ensure wavelength is 0.978565 Å, allowing slight rounding differences."""
        if isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                raise ValueError(f"Invalid value for wavelength: {value}. It must be a valid float.")
        target_wavelength = 0.978565
        if not math.isclose(value, target_wavelength, rel_tol=1e-4):
            raise ValueError("Wavelength must be 0.978565 Å.")
        return value

    @model_validator(mode="after")
    def validate_scan_range(cls, instance):
        """
        Ensure that `scan_range` is greater than or equal to `img_width` and is a multiple of `img_width`.
        """
        try:
            scan_range = float(instance.scan_range)
            img_width = float(instance.img_width)
        except ValueError:
            raise ValueError("Invalid input: scan_range and img_width must be numbers.")
        if scan_range < img_width:
            raise ValueError(f"Scan range ({scan_range}) cannot be smaller than image width ({img_width}).")
        divider = 1.0 % 0.1
        if math.isclose(divider, 0.0, abs_tol=1e-9):
            raise ValueError(
                f"Scan range ({scan_range}) must be a multiple of image width ({img_width})."
            )
        return instance
