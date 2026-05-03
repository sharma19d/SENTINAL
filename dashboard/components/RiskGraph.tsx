'use client';

import { useEffect, useRef } from 'react';
import * as d3 from 'd3';

interface Device {
  device_id: string;
  vendor: string;
  risk_score: number;
}

export default function RiskGraph({ devices }: { devices: Device[] }) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || devices.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    const simulation = d3.forceSimulation(devices as any)
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(50));

    const nodes = svg.append('g')
      .selectAll('circle')
      .data(devices)
      .enter()
      .append('g')
      .call(d3.drag<any, any>()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended) as any);

    nodes.append('circle')
      .attr('r', d => 10 + (d.risk_score * 3))
      .attr('fill', d => d.risk_score > 7 ? '#ef4444' : d.risk_score > 4 ? '#f59e0b' : '#10b981')
      .attr('stroke', '#fff')
      .attr('stroke-width', 2);

    nodes.append('text')
      .text(d => d.vendor || 'Unknown')
      .attr('dy', 30)
      .attr('text-anchor', 'middle')
      .attr('class', 'text-xs fill-white pointer-events-none font-medium');

    simulation.on('tick', () => {
      nodes.attr('transform', (d: any) => `translate(${d.x}, ${d.y})`);
    });

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

  }, [devices]);

  return <svg ref={svgRef} className="w-full h-full bg-slate-900 rounded-xl" />;
}
