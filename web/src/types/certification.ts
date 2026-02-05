export type CertificationType =
  | 'cloud-practitioner'
  | 'solutions-architect-associate'
  | 'solutions-architect-professional'
  | 'developer-associate'
  | 'sysops-administrator-associate'
  | 'devops-engineer-professional'
  | 'database-specialty'
  | 'security-specialty'
  | 'machine-learning-specialty'
  | 'data-analytics-specialty'
  | 'advanced-networking-specialty'
  | 'sap-specialty';

export interface CertificationInfo {
  id: CertificationType;
  name: string;
  hashtag: string;
  level: 'foundational' | 'associate' | 'professional' | 'specialty';
}

export const CERTIFICATIONS: CertificationInfo[] = [
  { id: 'cloud-practitioner', name: 'Cloud Practitioner', hashtag: 'CloudPractitioner', level: 'foundational' },
  { id: 'solutions-architect-associate', name: 'Solutions Architect Associate', hashtag: 'SolutionsArchitect', level: 'associate' },
  { id: 'solutions-architect-professional', name: 'Solutions Architect Professional', hashtag: 'SolutionsArchitect', level: 'professional' },
  { id: 'developer-associate', name: 'Developer Associate', hashtag: 'AWSDeveloper', level: 'associate' },
  { id: 'sysops-administrator-associate', name: 'SysOps Administrator Associate', hashtag: 'SysOpsAdmin', level: 'associate' },
  { id: 'devops-engineer-professional', name: 'DevOps Engineer Professional', hashtag: 'DevOpsEngineer', level: 'professional' },
  { id: 'database-specialty', name: 'Database Specialty', hashtag: 'AWSDatabase', level: 'specialty' },
  { id: 'security-specialty', name: 'Security Specialty', hashtag: 'AWSSecurity', level: 'specialty' },
  { id: 'machine-learning-specialty', name: 'Machine Learning Specialty', hashtag: 'AWSML', level: 'specialty' },
  { id: 'data-analytics-specialty', name: 'Data Analytics Specialty', hashtag: 'AWSAnalytics', level: 'specialty' },
  { id: 'advanced-networking-specialty', name: 'Advanced Networking Specialty', hashtag: 'AWSNetworking', level: 'specialty' },
  { id: 'sap-specialty', name: 'SAP on AWS Specialty', hashtag: 'AWSSAP', level: 'specialty' },
];

export interface CertificationSubmission {
  memberName: string;
  certificationType: CertificationType;
  certificationDate: string;
  photoUrl?: string;
  linkedinUrl?: string;
  personalMessage?: string;
  channels: Channel[];
}

export type Channel = 'facebook' | 'instagram' | 'linkedin' | 'whatsapp';

export interface SubmissionResponse {
  id: string;
  status: 'scheduled' | 'processing' | 'delivered' | 'failed';
  deliveries?: ChannelDelivery[];
}

export interface ChannelDelivery {
  channel: Channel;
  status: 'pending' | 'delivered' | 'failed';
  externalPostId?: string;
  error?: string;
  deliveredAt?: string;
}
