import { describe, it, expect } from 'vitest';
import { CERTIFICATIONS } from './certification';

describe('CERTIFICATIONS', () => {
  it('contains all 12 AWS certification types', () => {
    expect(CERTIFICATIONS).toHaveLength(12);
  });

  it('has unique IDs for each certification', () => {
    const ids = CERTIFICATIONS.map((c) => c.id);
    const uniqueIds = new Set(ids);
    expect(uniqueIds.size).toBe(CERTIFICATIONS.length);
  });

  it('has correct levels for each certification', () => {
    const foundational = CERTIFICATIONS.filter((c) => c.level === 'foundational');
    const associate = CERTIFICATIONS.filter((c) => c.level === 'associate');
    const professional = CERTIFICATIONS.filter((c) => c.level === 'professional');
    const specialty = CERTIFICATIONS.filter((c) => c.level === 'specialty');

    expect(foundational).toHaveLength(1);
    expect(associate).toHaveLength(3);
    expect(professional).toHaveLength(2);
    expect(specialty).toHaveLength(6);
  });

  it('includes Cloud Practitioner as foundational', () => {
    const cp = CERTIFICATIONS.find((c) => c.id === 'cloud-practitioner');
    expect(cp).toBeDefined();
    expect(cp?.level).toBe('foundational');
    expect(cp?.name).toBe('Cloud Practitioner');
  });

  it('includes Solutions Architect at both levels', () => {
    const saa = CERTIFICATIONS.find((c) => c.id === 'solutions-architect-associate');
    const sap = CERTIFICATIONS.find((c) => c.id === 'solutions-architect-professional');

    expect(saa?.level).toBe('associate');
    expect(sap?.level).toBe('professional');
  });

  it('has hashtags for all certifications', () => {
    CERTIFICATIONS.forEach((cert) => {
      expect(cert.hashtag).toBeTruthy();
      expect(cert.hashtag.length).toBeGreaterThan(0);
    });
  });
});
