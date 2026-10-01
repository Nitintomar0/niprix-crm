"use client";

import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import { useEffect } from "react";

function Recenter({ latitude, longitude }: { latitude: number; longitude: number }) {
  const map = useMap();
  useEffect(() => { map.setView([latitude, longitude], Math.max(map.getZoom(), 15), { animate: true }); }, [latitude, longitude, map]);
  return null;
}
function OpenOnClick({ onOpen }: { onOpen: () => void }) { useMapEvents({ click: onOpen }); return null; }

export function LiveLocationMap({ latitude, longitude, onOpen }: { latitude: number; longitude: number; onOpen: () => void }) {
  return <div className="h-[300px] overflow-hidden rounded-xl border border-[#dce6f0] sm:h-[360px]">
    <MapContainer center={[latitude, longitude]} zoom={15} scrollWheelZoom className="h-full w-full" aria-label="Employee current live location">
      <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <Recenter latitude={latitude} longitude={longitude} />
      <OpenOnClick onOpen={onOpen} />
      <CircleMarker center={[latitude, longitude]} radius={11} pathOptions={{ color: "#ffffff", weight: 3, fillColor: "#0869d8", fillOpacity: 1 }}>
        <Tooltip direction="top" offset={[0, -12]} opacity={1}>Current reported position</Tooltip>
      </CircleMarker>
    </MapContainer>
  </div>;
}
