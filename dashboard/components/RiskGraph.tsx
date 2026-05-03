'use client';

import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { 
  Camera, Lightbulb, Tv, Router, Shield, Cpu, 
  Smartphone, Laptop, Wifi, Bug, Ghost, XCircle 
} from 'lucide-react';
import { renderToStaticMarkup } from 'react-dom/server';

interface Device {
  device_id: string;
  vendor: string;
  ip: string;
  risk_score: number;
  is_quarantined?: boolean;
}

// Map vendors/types to icons
const getDeviceIcon = (vendor: string | null = '', isHoneypot: boolean = false) => {
  if (isHoneypot) return <Bug size={24} />;
  const v = (vendor || '').toLowerCase();
  if (v.includes('hikvision') || v.includes('camera')) return <Camera size={24} />;
  if (v.includes('tplink') || v.includes('router')) return <Router size={24} />;
  if (v.includes('bulb') || v.includes('philips')) return <Lightbulb size={24} />;
  if (v.includes('tv') || v.includes('samsung') || v.includes('lg')) return <Tv size={24} />;
  if (v.includes('apple') || v.includes('iphone') || v.includes('android')) return <Smartphone size={24} />;
  if (v.includes('sentinel')) return <Shield size={24} />;
  return <Cpu size={24} />;
};

const getSeverityColor = (score: number) => {
  if (score >= 9) return '#F43F5E'; // Rose
  if (score >= 8) return '#FB923C'; // Orange
  if (score >= 6) return '#F59E0B'; // Amber
  if (score >= 4) return '#FCD34D'; // Bright Amber
  if (score >= 3) return '#34D399'; // Light Emerald
  return '#10B981'; // Emerald
};

export default function RiskGraph({ 
  devices, 
  onSelectDevice 
}: { 
  devices: Device[], 
  onSelectDevice: (d: Device) => void 
}) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || devices.length === 0) return;

    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    // ── Setup Simulation ───────────────────────────────────────
    
    // Add SENTINEL node as the center
    const nodes = [
      { device_id: 'sentinel-core', vendor: 'SENTINEL', risk_score: 0, isSentinel: true, x: width/2, y: height/2 },
      ...devices.map(d => ({ ...d }))
    ];

    const links = devices.map(d => ({
      source: 'sentinel-core',
      target: d.device_id
    }));

    const simulation = d3.forceSimulation(nodes as any)
      .force('link', d3.forceLink(links).id((d: any) => d.device_id).distance(200))
      .force('charge', d3.forceManyBody().strength(-800))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(80));

    // ── Render Links (Edges) ──────────────────────────────────
    
    const link = svg.append('g')
      .selectAll('line')
      .data(links)
      .enter()
      .append('line')
      .attr('stroke', '#253552')
      .attr('stroke-width', 1.5)
      .attr('stroke-dasharray', '5,5');

    // ── Render Nodes ──────────────────────────────────────────
    
    const node = svg.append('g')
      .selectAll('g')
      .data(nodes)
      .enter()
      .append('g')
      .attr('class', (d: any) => d.isSentinel ? '' : 'cursor-pointer')
      .on('click', (event, d: any) => !d.isSentinel && onSelectDevice(d))
      .call(d3.drag<any, any>()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended) as any);

    // Node Circles
    node.append('circle')
      .attr('r', (d: any) => d.isSentinel ? 40 : 25 + (d.risk_score * 2))
      .attr('fill', '#101829')
      .attr('stroke', (d: any) => d.isSentinel ? '#F59E0B' : getSeverityColor(d.risk_score))
      .attr('stroke-width', 2.5)
      .attr('class', (d: any) => {
        if (d.risk_score >= 8) return 'animate-threat';
        if (!d.isSentinel && d.risk_score < 4) return 'animate-breathe';
        return '';
      });

    // Icons
    node.append('foreignObject')
      .attr('x', (d: any) => d.isSentinel ? -20 : -15)
      .attr('y', (d: any) => d.isSentinel ? -20 : -15)
      .attr('width', (d: any) => d.isSentinel ? 40 : 30)
      .attr('height', (d: any) => d.isSentinel ? 40 : 30)
      .html((d: any) => {
        const icon = getDeviceIcon(d.vendor);
        const color = d.isSentinel ? '#F59E0B' : getSeverityColor(d.risk_score);
        return renderToStaticMarkup(
          <div style={{ color, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            {icon}
          </div>
        );
      });

    // Quarantined Overlay
    node.filter((d: any) => d.is_quarantined)
      .append('foreignObject')
      .attr('x', 10)
      .attr('y', -30)
      .attr('width', 24)
      .attr('height', 24)
      .html(() => renderToStaticMarkup(<XCircle color="#F43F5E" size={20} fill="#060A12" />));

    // ── Update Positions ──────────────────────────────────────

    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      node.attr('transform', (d: any) => `translate(${d.x}, ${d.y})`);
    });

    // ── Drag Functions ────────────────────────────────────────

    function dragstarted(event: any) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }

    function dragged(event: any) {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    }

    function dragended(event: any) {
      if (!event.active) simulation.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    }

  }, [devices, onSelectDevice]);

  return (
    <div className="w-full h-full relative">
      <svg ref={svgRef} className="w-full h-full" />
      
      {/* Legend / Controls */}
      <div className="absolute bottom-6 right-6 flex flex-col gap-2">
        <div className="bg-bg-surface/80 backdrop-blur-md border border-border-subtle p-3 rounded-xl space-y-2">
          <p className="text-[10px] text-text-muted font-bold uppercase tracking-wider">Topology Key</p>
          <div className="flex items-center gap-2 text-[10px] text-text-secondary">
             <div className="w-2 h-2 rounded-full bg-safe" /> Healthy Device
          </div>
          <div className="flex items-center gap-2 text-[10px] text-text-secondary">
             <div className="w-2 h-2 rounded-full bg-warning" /> Anomaly/Risk
          </div>
          <div className="flex items-center gap-2 text-[10px] text-text-secondary">
             <div className="w-2 h-2 rounded-full bg-critical" /> Active Threat
          </div>
        </div>
      </div>
    </div>
  );
}
