// Well coordinate type
export interface WellCoordinates {
  longitude: number;
  latitude: number;
}

// From our API shape (mirrors Python WellLogData / WellMetadata)
export interface WellLocation extends WellCoordinates {
  well_id: string;
  well_name: string;
}