import { useState } from 'react';
import { Calendar, User, Link as LinkIcon, MessageSquare, Image } from 'lucide-react';
import {
  CERTIFICATIONS,
  type CertificationSubmission,
  type CertificationType,
  type Channel,
} from '../types/certification';

interface Props {
  onSubmit: (submission: CertificationSubmission) => void;
  onChange: (submission: Partial<CertificationSubmission>) => void;
  isSubmitting: boolean;
}

const CHANNELS: { id: Channel; name: string; icon: string }[] = [
  { id: 'facebook', name: 'Facebook', icon: '📘' },
  { id: 'instagram', name: 'Instagram', icon: '📸' },
  { id: 'linkedin', name: 'LinkedIn', icon: '💼' },
  { id: 'whatsapp', name: 'WhatsApp', icon: '💬' },
];

export function CertificationForm({ onSubmit, onChange, isSubmitting }: Props) {
  const [memberName, setMemberName] = useState('');
  const [certificationType, setCertificationType] = useState<CertificationType | ''>('');
  const [certificationDate, setCertificationDate] = useState('');
  const [photoUrl, setPhotoUrl] = useState('');
  const [linkedinUrl, setLinkedinUrl] = useState('');
  const [personalMessage, setPersonalMessage] = useState('');
  const [selectedChannels, setSelectedChannels] = useState<Channel[]>(['facebook', 'linkedin']);

  const handleChange = (updates: Partial<CertificationSubmission>) => {
    onChange({
      memberName,
      certificationType: certificationType || undefined,
      certificationDate,
      photoUrl: photoUrl || undefined,
      linkedinUrl: linkedinUrl || undefined,
      personalMessage: personalMessage || undefined,
      channels: selectedChannels,
      ...updates,
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!certificationType) return;

    onSubmit({
      memberName,
      certificationType,
      certificationDate,
      photoUrl: photoUrl || undefined,
      linkedinUrl: linkedinUrl || undefined,
      personalMessage: personalMessage || undefined,
      channels: selectedChannels,
    });
  };

  const toggleChannel = (channel: Channel) => {
    const newChannels = selectedChannels.includes(channel)
      ? selectedChannels.filter((c) => c !== channel)
      : [...selectedChannels, channel];
    setSelectedChannels(newChannels);
    handleChange({ channels: newChannels });
  };

  const groupedCerts = {
    foundational: CERTIFICATIONS.filter((c) => c.level === 'foundational'),
    associate: CERTIFICATIONS.filter((c) => c.level === 'associate'),
    professional: CERTIFICATIONS.filter((c) => c.level === 'professional'),
    specialty: CERTIFICATIONS.filter((c) => c.level === 'specialty'),
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <label htmlFor="memberName" className="block text-sm font-medium text-gray-700 mb-1">
          <User className="inline h-4 w-4 mr-1" />
          Full Name *
        </label>
        <input
          type="text"
          id="memberName"
          required
          value={memberName}
          onChange={(e) => {
            setMemberName(e.target.value);
            handleChange({ memberName: e.target.value });
          }}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff9900] focus:border-transparent"
          placeholder="John Doe"
        />
      </div>

      <div>
        <label htmlFor="certificationType" className="block text-sm font-medium text-gray-700 mb-1">
          Certification Type *
        </label>
        <select
          id="certificationType"
          required
          value={certificationType}
          onChange={(e) => {
            const value = e.target.value as CertificationType;
            setCertificationType(value);
            handleChange({ certificationType: value });
          }}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff9900] focus:border-transparent"
        >
          <option value="">Select a certification...</option>
          <optgroup label="Foundational">
            {groupedCerts.foundational.map((cert) => (
              <option key={cert.id} value={cert.id}>
                {cert.name}
              </option>
            ))}
          </optgroup>
          <optgroup label="Associate">
            {groupedCerts.associate.map((cert) => (
              <option key={cert.id} value={cert.id}>
                {cert.name}
              </option>
            ))}
          </optgroup>
          <optgroup label="Professional">
            {groupedCerts.professional.map((cert) => (
              <option key={cert.id} value={cert.id}>
                {cert.name}
              </option>
            ))}
          </optgroup>
          <optgroup label="Specialty">
            {groupedCerts.specialty.map((cert) => (
              <option key={cert.id} value={cert.id}>
                {cert.name}
              </option>
            ))}
          </optgroup>
        </select>
      </div>

      <div>
        <label htmlFor="certificationDate" className="block text-sm font-medium text-gray-700 mb-1">
          <Calendar className="inline h-4 w-4 mr-1" />
          Certification Date *
        </label>
        <input
          type="date"
          id="certificationDate"
          required
          value={certificationDate}
          onChange={(e) => {
            setCertificationDate(e.target.value);
            handleChange({ certificationDate: e.target.value });
          }}
          max={new Date().toISOString().split('T')[0]}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff9900] focus:border-transparent"
        />
      </div>

      <div>
        <label htmlFor="photoUrl" className="block text-sm font-medium text-gray-700 mb-1">
          <Image className="inline h-4 w-4 mr-1" />
          Photo URL (optional)
        </label>
        <input
          type="url"
          id="photoUrl"
          value={photoUrl}
          onChange={(e) => {
            setPhotoUrl(e.target.value);
            handleChange({ photoUrl: e.target.value });
          }}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff9900] focus:border-transparent"
          placeholder="https://example.com/badge.png"
        />
        <p className="text-xs text-gray-500 mt-1">Link to your badge image or celebration photo</p>
      </div>

      <div>
        <label htmlFor="linkedinUrl" className="block text-sm font-medium text-gray-700 mb-1">
          <LinkIcon className="inline h-4 w-4 mr-1" />
          LinkedIn Profile URL (optional)
        </label>
        <input
          type="url"
          id="linkedinUrl"
          value={linkedinUrl}
          onChange={(e) => {
            setLinkedinUrl(e.target.value);
            handleChange({ linkedinUrl: e.target.value });
          }}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff9900] focus:border-transparent"
          placeholder="https://linkedin.com/in/johndoe"
        />
      </div>

      <div>
        <label htmlFor="personalMessage" className="block text-sm font-medium text-gray-700 mb-1">
          <MessageSquare className="inline h-4 w-4 mr-1" />
          Personal Message (optional)
        </label>
        <textarea
          id="personalMessage"
          value={personalMessage}
          onChange={(e) => {
            setPersonalMessage(e.target.value);
            handleChange({ personalMessage: e.target.value });
          }}
          rows={3}
          maxLength={280}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff9900] focus:border-transparent resize-none"
          placeholder="Share your journey or tips for others..."
        />
        <p className="text-xs text-gray-500 mt-1">{personalMessage.length}/280 characters</p>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Post to Channels *
        </label>
        <div className="flex flex-wrap gap-2">
          {CHANNELS.map((channel) => (
            <button
              key={channel.id}
              type="button"
              onClick={() => toggleChannel(channel.id)}
              className={`px-4 py-2 rounded-lg border-2 transition-all ${
                selectedChannels.includes(channel.id)
                  ? 'border-[#ff9900] bg-[#ff9900]/10 text-[#232f3e]'
                  : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
              }`}
            >
              <span className="mr-1">{channel.icon}</span>
              {channel.name}
            </button>
          ))}
        </div>
        {selectedChannels.length === 0 && (
          <p className="text-xs text-red-500 mt-1">Select at least one channel</p>
        )}
      </div>

      <button
        type="submit"
        disabled={isSubmitting || selectedChannels.length === 0 || !certificationType}
        className="w-full py-3 px-4 bg-[#ff9900] hover:bg-[#ec7211] disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors"
      >
        {isSubmitting ? 'Submitting...' : '🎉 Announce My Certification'}
      </button>
    </form>
  );
}
