import React, { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';

export default function DynamicCurrentsOverlay({ showCurrents = true }) {
  const map = useMap();
  const canvasRef = useRef(null);
  const animationRef = useRef(null);
  const particlesRef = useRef([]);

  useEffect(() => {
    if (!showCurrents) {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      if (canvasRef.current) {
        const ctx = canvasRef.current.getContext('2d');
        ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
      }
      return;
    }

    const container = map.getContainer();
    const canvas = document.createElement('canvas');
    canvas.style.position = 'absolute';
    canvas.style.top = '0';
    canvas.style.left = '0';
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    canvas.style.pointerEvents = 'none';
    canvas.style.zIndex = '350'; 
    container.appendChild(canvas);
    canvasRef.current = canvas;

    const ctx = canvas.getContext('2d');

    const resizeCanvas = () => {
      const size = map.getSize();
      canvas.width = size.x;
      canvas.height = size.y;
    };
    resizeCanvas();

    const bounds = map.getBounds();
    const southWest = bounds.getSouthWest();
    const northEast = bounds.getNorthEast();

    const particleCount = 180;
    const particles = [];
    for (let i = 0; i < particleCount; i++) {
      particles.push({
        lat: southWest.lat + Math.random() * (northEast.lat - southWest.lat),
        lng: southWest.lng + Math.random() * (northEast.lng - southWest.lng),
        life: 60 + Math.random() * 100,
        age: 0,
        speed: 0.008 + Math.random() * 0.015,
      });
    }
    particlesRef.current = particles;

    const getFlowVector = (lat, lng) => {
      const bobCenter = { lat: 14.0, lng: 88.0 };
      const asCenter = { lat: 14.0, lng: 68.0 };

      if (lng > 78) {
        const dLat = lat - bobCenter.lat;
        const dLng = lng - bobCenter.lng;
        return {
          u: -dLat * 0.04 + Math.sin(lat * 4) * 0.015,
          v: dLng * 0.04 + Math.cos(lng * 4) * 0.015
        };
      } else {
        const dLat = lat - asCenter.lat;
        const dLng = lng - asCenter.lng;
        return {
          u: -dLat * 0.05 + Math.cos(lat * 3) * 0.02,
          v: dLng * 0.05 + Math.sin(lng * 3) * 0.02
        };
      }
    };

    const draw = () => {
      ctx.fillStyle = 'rgba(15, 23, 42, 0.06)'; 
      ctx.globalCompositeOperation = 'destination-in';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.globalCompositeOperation = 'source-over';

      const currentBounds = map.getBounds();
      const sw = currentBounds.getSouthWest();
      const ne = currentBounds.getNorthEast();
      const zoom = map.getZoom();

      // Dynamically scale step size and viewport margins based on zoom
      const zoomScale = Math.pow(2, zoom - 11);
      const marginLat = (ne.lat - sw.lat) * 0.1;
      const marginLng = (ne.lng - sw.lng) * 0.1;

      particles.forEach((p) => {
        const flow = getFlowVector(p.lat, p.lng);
        const ptStart = map.latLngToContainerPoint([p.lat, p.lng]);

        // Scale velocity so speed in screen pixels remains constant
        const stepLat = (flow.v * p.speed) / zoomScale;
        const stepLng = (flow.u * p.speed) / zoomScale;

        p.lat += stepLat;
        p.lng += stepLng;
        p.age++;

        const ptEnd = map.latLngToContainerPoint([p.lat, p.lng]);

        const speedMag = Math.sqrt(flow.u * flow.u + flow.v * flow.v);
        let strokeColor = 'rgba(6, 182, 214, 0.45)'; 
        if (speedMag > 0.4) {
          strokeColor = 'rgba(34, 197, 94, 0.5)'; 
        } else if (speedMag < 0.15) {
          strokeColor = 'rgba(56, 189, 248, 0.35)'; 
        }

        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = 1.5;

        if (
          ptStart.x >= 0 && ptStart.x <= canvas.width &&
          ptStart.y >= 0 && ptStart.y <= canvas.height
        ) {
          ctx.beginPath();
          ctx.moveTo(ptStart.x, ptStart.y);
          ctx.lineTo(ptEnd.x, ptEnd.y);
          ctx.stroke();
        }

        // Reset particle if it exceeds age or goes beyond proportional viewport margin
        if (
          p.age > p.life ||
          p.lat < sw.lat - marginLat || p.lat > ne.lat + marginLat ||
          p.lng < sw.lng - marginLng || p.lng > ne.lng + marginLng
        ) {
          p.lat = sw.lat + Math.random() * (ne.lat - sw.lat);
          p.lng = sw.lng + Math.random() * (ne.lng - sw.lng);
          p.age = 0;
          p.life = 60 + Math.random() * 100;
        }
      });

      animationRef.current = requestAnimationFrame(draw);
    };

    map.on('move', resizeCanvas);
    map.on('resize', resizeCanvas);

    draw();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      map.off('move', resizeCanvas);
      map.off('resize', resizeCanvas);
      if (canvas.parentNode) {
        canvas.parentNode.removeChild(canvas);
      }
    };
  }, [map, showCurrents]);

  return null;
}
