import { CERTIFICATIONS, type CertificationSubmission, type Channel } from '../types/certification';

export function generatePost(submission: CertificationSubmission, channel: Channel): string {
  const cert = CERTIFICATIONS.find((c) => c.id === submission.certificationType);
  if (!cert) return '';

  const name = submission.memberName;
  const certName = cert.name;
  const hashtag = cert.hashtag;
  const personalMessage = submission.personalMessage?.trim();

  switch (channel) {
    case 'facebook':
      return generateFacebookPost(name, certName, hashtag, personalMessage);
    case 'instagram':
      return generateInstagramPost(name, certName, hashtag, personalMessage);
    case 'linkedin':
      return generateLinkedInPost(name, certName, hashtag, personalMessage, submission.linkedinUrl);
    case 'whatsapp':
      return generateWhatsAppPost(name, certName, personalMessage);
    default:
      return '';
  }
}

function generateFacebookPost(
  name: string,
  certName: string,
  hashtag: string,
  personalMessage?: string
): string {
  let post = `🎉 Congratulations to ${name}! 🎉\n\n`;
  post += `${name} has just earned the AWS ${certName} certification!\n\n`;
  if (personalMessage) {
    post += `"${personalMessage}"\n\n`;
  }
  post += `Welcome to the club of AWS certified professionals! 🚀\n\n`;
  post += `#AWSCertified #${hashtag} #CloudCommunity #AWSCommunity`;
  return post;
}

function generateInstagramPost(
  name: string,
  certName: string,
  hashtag: string,
  personalMessage?: string
): string {
  let post = `🎉 Huge congrats to ${name}! 🎉\n\n`;
  post += `Just earned the AWS ${certName} certification! ☁️✨\n\n`;
  if (personalMessage) {
    post += `"${personalMessage}"\n\n`;
  }
  post += `Welcome to the AWS certified fam! 🚀💪\n\n`;
  post += `.\n.\n.\n`;
  post += `#AWSCertified #${hashtag} #CloudCommunity #AWSCommunity #TechCommunity #CloudComputing #AWS #Certification`;
  return post;
}

function generateLinkedInPost(
  name: string,
  certName: string,
  hashtag: string,
  personalMessage?: string,
  linkedinUrl?: string
): string {
  let post = `🎉 Congratulations to ${name}!\n\n`;
  post += `We're thrilled to announce that ${name} has achieved the AWS ${certName} certification.\n\n`;
  if (personalMessage) {
    post += `${name} shares: "${personalMessage}"\n\n`;
  }
  if (linkedinUrl) {
    post += `Connect with ${name}: ${linkedinUrl}\n\n`;
  }
  post += `This achievement demonstrates dedication to cloud excellence. Welcome to our growing community of AWS certified professionals!\n\n`;
  post += `#AWSCertified #${hashtag} #CloudComputing #ProfessionalDevelopment`;
  return post;
}

function generateWhatsAppPost(name: string, certName: string, personalMessage?: string): string {
  let post = `🎉 *Congratulations ${name}!*\n\n`;
  post += `Just earned the *AWS ${certName}* certification!\n\n`;
  if (personalMessage) {
    post += `_"${personalMessage}"_\n\n`;
  }
  post += `Welcome to the club! 🚀`;
  return post;
}
