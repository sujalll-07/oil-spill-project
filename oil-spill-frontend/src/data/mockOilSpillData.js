import { offshoreRigsGeoJSON } from './offshoreRigsData';

export const mockSpill = {
  id: 'SPILL-2025-05-25-0012',
  detectionTime: '25 May 2025 06:12 UTC',
  satellite: 'Sentinel-1A SAR',
  sensorType: 'C-Band Synthetic Aperture Radar',
  lat: 16.5000,
  lng: 86.5000,
  areaKm2: 18,
  confidencePct: 92,
  oilType: 'Unknown (Heavy Crude suspected)',
  windSpeedKmh: 16,
  windDirectionDeg: 292,
  windDirectionLabel: 'WNW (292°)',
  polygon: [
    [16.5108, 86.4822], [16.5138, 86.4972], [16.5078, 86.5172],
    [16.4968, 86.5242], [16.4858, 86.5122], [16.4838, 86.4922],
    [16.4908, 86.4772], [16.5038, 86.4742],
  ],
};

export const mockVessels = [
  {
    id: 'v1', name: 'Tanker XYZ', imo: '9387654', mmsi: '123456789',
    callsign: 'V7A29', flag: 'Panama', type: 'Oil Tanker',
    navStatus: 'Underway using Engine', sog: 12.6, cog: 145,
    lengthM: 260, beamM: 45, draftM: 14.2, destination: 'ROTTERDAM',
    eta: '2025-06-02 14:00 UTC', distanceKm: 4.2,
    lat: 16.4908, lng: 86.4742, isSuspect: true, suspicionScore: 94,
    trajectory: [[16.5208, 86.4442], [16.5058, 86.4602], [16.4908, 86.4742]],
  },
  {
    id: 'v2', name: 'Cargo Ship ABC', imo: '9134560', mmsi: '256789000',
    callsign: 'C4B71', flag: 'Liberia', type: 'Cargo Ship',
    navStatus: 'Underway using Engine', sog: 14.1, cog: 210,
    lengthM: 199, beamM: 32, draftM: 11.0, destination: 'CHITTAGONG',
    eta: '2025-05-29 09:00 UTC', distanceKm: 7.8,
    lat: 16.5208, lng: 86.5322, isSuspect: false,
  },
  {
    id: 'v3', name: 'Fishing Vessel DEF', imo: '8765432', mmsi: '279456800',
    callsign: 'F2D19', flag: 'India', type: 'Fishing Vessel',
    navStatus: 'Engaged in Fishing', sog: 6.3, cog: 300,
    lengthM: 32, beamM: 8, draftM: 3.5, destination: 'N/A',
    eta: 'N/A', distanceKm: 9.6,
    lat: 16.5158, lng: 86.4622, isSuspect: false,
  },
  {
    id: 'v4', name: 'Cargo Ship GHI', imo: '9071230', mmsi: '273456780',
    callsign: 'C8H45', flag: 'Panama', type: 'Cargo Ship',
    navStatus: 'Underway using Engine', sog: 13.4, cog: 95,
    lengthM: 185, beamM: 30, draftM: 10.4, destination: 'SINGAPORE',
    eta: '2025-06-04 18:00 UTC', distanceKm: 11.3,
    lat: 16.4808, lng: 86.4672, isSuspect: false,
  },
];

// Convert the static GeoJSON rig catalog to the shape consumed by PlatformMarker.
export const offshorePlatformsData = (offshoreRigsGeoJSON?.features || []).map((feature) => ({
  id: feature.properties.id || feature.id,
  name: feature.properties.name,
  operator: feature.properties.operator,
  field: feature.properties.field,
  basin: feature.properties.basin,
  region: feature.properties.region,
  jurisdiction: feature.properties.jurisdiction,
  isIndiaEEZ: feature.properties.isIndiaEEZ !== false,
  type: feature.properties.type,
  status: feature.properties.status,
  waterDepthM: feature.properties.waterDepthM,
  installedYear: feature.properties.installedYear,
  coordinatesVerified: feature.properties.coordinatesVerified !== false,
  coordinateSource: feature.properties.coordinateSource,
  lat: feature.geometry.coordinates[1],
  lng: feature.geometry.coordinates[0],
}));

export const mockPlatforms = offshorePlatformsData;
