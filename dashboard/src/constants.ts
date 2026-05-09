import { Screen, Threat, Device, FirewallRule } from './types';

export const THREATS: Threat[] = [
  {
    id: '1',
    time: '14:02:45 UTC',
    code: 'T1046: Network Service Scanning',
    title: 'Anomalous internal port sweep originating from DMZ node.',
    description: 'AI heuristics indicate potential lateral movement attempting to identify exposed RDP services across the engineering subnet.',
    severity: 10,
    source: '192.168.50.12',
    sourceDetail: '(DMZ-PROXY-01)',
    target: '10.0.0.0/24',
    targetDetail: '(ENG-SUBNET)',
    action: 'Auto-Isolated Source Node',
  },
  {
    id: '2',
    time: '13:58:12 UTC',
    code: 'T1110: Brute Force',
    title: 'Sustained login failures on Edge Gateway.',
    description: 'Pattern matches dictionary attack signature. Rate limit threshold exceeded.',
    severity: 7,
    source: '45.22.109.11',
    sourceDetail: '(External)',
    target: 'gw.edge.sentinel.net:443',
    targetDetail: '',
    action: 'IP Temp-Banned (1hr)',
  },
  {
    id: '3',
    time: '13:15:00 UTC',
    code: 'T1078: Valid Accounts',
    title: 'Anomalous geo-location login.',
    description: "User 'admin.sys' authenticated from unexpected region (EU) while active session exists in US.",
    severity: 4,
    source: '89.144.2.1',
    sourceDetail: '(DE)',
    target: 'admin.sys',
    targetDetail: '',
    action: 'Flagged for Review',
  }
];

export const DEVICES: Device[] = [
  {
    id: '1',
    name: 'Exec_Boardroom_Display',
    vendor: 'Samsung Electronics',
    ip: '10.4.12.88',
    mac: 'DC:A9:04:88:F2:1A',
    riskScore: 8.9,
    ports: 4,
    cves: 12,
    isQuarantined: false,
    type: 'display',
  },
  {
    id: '2',
    name: 'Lobby_Cam_04',
    vendor: 'Hikvision Digital',
    ip: '10.2.55.12',
    mac: '00:40:8C:1A:2B:3C',
    riskScore: 5.2,
    ports: 2,
    cves: 0,
    isQuarantined: true,
    type: 'camera',
  },
  {
    id: '3',
    name: 'Eng_MacBook_Pro',
    vendor: 'Apple, Inc.',
    ip: '192.168.1.104',
    mac: 'F8:FF:C2:E1:99:A0',
    riskScore: 1.4,
    ports: 0,
    cves: 0,
    isQuarantined: false,
    type: 'laptop',
  }
];

export const FIREWALL_RULES: FirewallRule[] = [
  { id: '1', ruleId: '#FW-892A', protocol: 'TCP/22', target: '0.0.0.0/0', action: 'DROP', status: true },
  { id: '2', ruleId: '#FW-441B', protocol: 'ICMP', target: 'Internal_Subnet', action: 'REJECT', status: true },
  { id: '3', ruleId: '#FW-102C', protocol: 'UDP/53', target: '192.168.1.50', action: 'LOG_ONLY', status: false },
  { id: '4', ruleId: '#FW-999Z', protocol: 'TCP/443', target: 'Any', action: 'ACCEPT', status: true },
];
