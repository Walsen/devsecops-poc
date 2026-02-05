import { describe, it, expect } from 'vitest';
import { generatePost } from './postGenerator';
import type { CertificationSubmission } from '../types/certification';

describe('generatePost', () => {
  const baseSubmission: CertificationSubmission = {
    memberName: 'John Doe',
    certificationType: 'solutions-architect-associate',
    certificationDate: '2026-02-01',
    channels: ['facebook', 'linkedin'],
  };

  describe('Facebook posts', () => {
    it('generates a Facebook post with name and certification', () => {
      const post = generatePost(baseSubmission, 'facebook');

      expect(post).toContain('🎉 Congratulations to John Doe! 🎉');
      expect(post).toContain('AWS Solutions Architect Associate certification');
      expect(post).toContain('#AWSCertified');
      expect(post).toContain('#SolutionsArchitect');
    });

    it('includes personal message when provided', () => {
      const submission = {
        ...baseSubmission,
        personalMessage: 'Hard work pays off!',
      };
      const post = generatePost(submission, 'facebook');

      expect(post).toContain('"Hard work pays off!"');
    });
  });

  describe('LinkedIn posts', () => {
    it('generates a professional LinkedIn post', () => {
      const post = generatePost(baseSubmission, 'linkedin');

      expect(post).toContain('Congratulations to John Doe');
      expect(post).toContain('AWS Solutions Architect Associate certification');
      expect(post).toContain('#ProfessionalDevelopment');
    });

    it('includes LinkedIn URL when provided', () => {
      const submission = {
        ...baseSubmission,
        linkedinUrl: 'https://linkedin.com/in/johndoe',
      };
      const post = generatePost(submission, 'linkedin');

      expect(post).toContain('https://linkedin.com/in/johndoe');
    });
  });

  describe('Instagram posts', () => {
    it('generates an Instagram post with emojis and hashtags', () => {
      const post = generatePost(baseSubmission, 'instagram');

      expect(post).toContain('🎉 Huge congrats to John Doe! 🎉');
      expect(post).toContain('#TechCommunity');
      expect(post).toContain('#CloudComputing');
    });
  });

  describe('WhatsApp posts', () => {
    it('generates a concise WhatsApp message with formatting', () => {
      const post = generatePost(baseSubmission, 'whatsapp');

      expect(post).toContain('*Congratulations John Doe!*');
      expect(post).toContain('*AWS Solutions Architect Associate*');
      expect(post).toContain('🚀');
    });

    it('includes personal message in italics', () => {
      const submission = {
        ...baseSubmission,
        personalMessage: 'Never give up!',
      };
      const post = generatePost(submission, 'whatsapp');

      expect(post).toContain('_"Never give up!"_');
    });
  });

  describe('different certification types', () => {
    it('handles Cloud Practitioner', () => {
      const submission = {
        ...baseSubmission,
        certificationType: 'cloud-practitioner' as const,
      };
      const post = generatePost(submission, 'facebook');

      expect(post).toContain('Cloud Practitioner');
      expect(post).toContain('#CloudPractitioner');
    });

    it('handles Security Specialty', () => {
      const submission = {
        ...baseSubmission,
        certificationType: 'security-specialty' as const,
      };
      const post = generatePost(submission, 'facebook');

      expect(post).toContain('Security Specialty');
      expect(post).toContain('#AWSSecurity');
    });

    it('handles Machine Learning Specialty', () => {
      const submission = {
        ...baseSubmission,
        certificationType: 'machine-learning-specialty' as const,
      };
      const post = generatePost(submission, 'facebook');

      expect(post).toContain('Machine Learning Specialty');
      expect(post).toContain('#AWSML');
    });
  });
});
