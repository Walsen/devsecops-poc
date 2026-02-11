import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PostPreview } from './PostPreview';

describe('PostPreview', () => {
  it('shows placeholder when required fields are missing', () => {
    render(<PostPreview submission={{}} />);

    expect(screen.getByText('Fill in the form to see post previews')).toBeInTheDocument();
  });

  it('shows placeholder when no channels selected', () => {
    render(
      <PostPreview
        submission={{
          memberName: 'John Doe',
          certificationType: 'cloud-practitioner',
          certificationDate: '2026-02-01',
          channels: [],
        }}
      />
    );

    expect(screen.getByText('Select at least one channel to see previews')).toBeInTheDocument();
  });

  it('renders Facebook preview when selected', () => {
    render(
      <PostPreview
        submission={{
          memberName: 'Jane Smith',
          certificationType: 'solutions-architect-associate',
          certificationDate: '2026-02-01',
          channels: ['facebook'],
        }}
      />
    );

    expect(screen.getByText('Facebook Preview')).toBeInTheDocument();
    expect(screen.getByText(/Congratulations to Jane Smith/)).toBeInTheDocument();
  });

  it('renders multiple channel previews', () => {
    render(
      <PostPreview
        submission={{
          memberName: 'Test User',
          certificationType: 'developer-associate',
          certificationDate: '2026-02-01',
          channels: ['facebook', 'linkedin', 'instagram'],
        }}
      />
    );

    expect(screen.getByText('Facebook Preview')).toBeInTheDocument();
    expect(screen.getByText('LinkedIn Preview')).toBeInTheDocument();
    expect(screen.getByText('Instagram Preview')).toBeInTheDocument();
  });

  it('shows personal message in preview when provided', () => {
    render(
      <PostPreview
        submission={{
          memberName: 'Test User',
          certificationType: 'cloud-practitioner',
          certificationDate: '2026-02-01',
          channels: ['facebook'],
          personalMessage: 'This is my journey!',
        }}
      />
    );

    expect(screen.getByText(/This is my journey!/)).toBeInTheDocument();
  });
});
