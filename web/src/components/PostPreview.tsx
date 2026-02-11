import { Facebook, Instagram, Linkedin, MessageCircle } from 'lucide-react';
import type { Channel, CertificationSubmission } from '../types/certification';
import { generatePost } from '../utils/postGenerator';

interface Props {
  submission: Partial<CertificationSubmission>;
}

const CHANNEL_CONFIG: Record<Channel, { name: string; icon: React.ReactNode; bgColor: string }> = {
  facebook: {
    name: 'Facebook',
    icon: <Facebook className="h-5 w-5" />,
    bgColor: 'bg-[#1877f2]',
  },
  instagram: {
    name: 'Instagram',
    icon: <Instagram className="h-5 w-5" />,
    bgColor: 'bg-gradient-to-r from-[#833ab4] via-[#fd1d1d] to-[#fcb045]',
  },
  linkedin: {
    name: 'LinkedIn',
    icon: <Linkedin className="h-5 w-5" />,
    bgColor: 'bg-[#0a66c2]',
  },
  whatsapp: {
    name: 'WhatsApp',
    icon: <MessageCircle className="h-5 w-5" />,
    bgColor: 'bg-[#25d366]',
  },
};

export function PostPreview({ submission }: Props) {
  const channels = submission.channels || [];
  const hasRequiredFields =
    submission.memberName && submission.certificationType && submission.certificationDate;

  if (!hasRequiredFields) {
    return (
      <div className="bg-gray-100 rounded-lg p-8 text-center text-gray-500">
        <p>Fill in the form to see post previews</p>
      </div>
    );
  }

  if (channels.length === 0) {
    return (
      <div className="bg-gray-100 rounded-lg p-8 text-center text-gray-500">
        <p>Select at least one channel to see previews</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {channels.map((channel) => {
        const config = CHANNEL_CONFIG[channel];
        const postContent = generatePost(submission as CertificationSubmission, channel);

        return (
          <div key={channel} className="bg-white rounded-lg shadow-md overflow-hidden">
            <div className={`${config.bgColor} text-white px-4 py-2 flex items-center gap-2`}>
              {config.icon}
              <span className="font-medium">{config.name} Preview</span>
            </div>
            <div className="p-4">
              <pre className="whitespace-pre-wrap font-sans text-sm text-gray-700 leading-relaxed">
                {postContent}
              </pre>
              {submission.photoUrl && (
                <div className="mt-3 border rounded-lg overflow-hidden">
                  <img
                    src={submission.photoUrl}
                    alt="Certification badge"
                    className="w-full h-48 object-cover"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = 'none';
                    }}
                  />
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
