export enum Screen {
  DASHBOARD = 'dashboard',
  DEVICES = 'devices',
  THREATS = 'threats',
  FIREWALL = 'firewall',
  HONEYPOTS = 'honeypots',
  DIAGNOSTICS = 'diagnostics',
  LOGS = 'logs',
  SETTINGS = 'settings',
}

export interface Threat {
  id: string;
  time: string;
  code: string;
  title: string;
  description: string;
  severity: number;
  source: string;
  sourceDetail: string;
  target: string;
  targetDetail: string;
  action: string;
}

export interface Device {
  id: string;
  name: string;
  vendor: string;
  ip: string;
  mac: string;
  riskScore: number;
  ports: number;
  cves: number;
  isQuarantined: boolean;
  type: 'laptop' | 'camera' | 'display' | 'router';
}

export interface FirewallRule {
  id: string;
  ruleId: string;
  protocol: string;
  target: string;
  action: 'DROP' | 'REJECT' | 'LOG_ONLY' | 'ACCEPT';
  status: boolean;
}
