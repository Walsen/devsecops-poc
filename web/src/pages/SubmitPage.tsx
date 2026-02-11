import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { CertificationForm } from '../components/CertificationForm';
import { PostPreview } from '../components/PostPreview';
import { submitCertification } from '../api/client';
import type { CertificationSubmission } from '../types/certification';

export function SubmitPage() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<Partial<CertificationSubmission>>({});

  const mutation = useMutation({
    mutationFn: submitCertification,
    onSuccess: (data) => {
      navigate(`/success/${data.id}`);
    },
  });

  const handleSubmit = (submission: CertificationSubmission) => {
    mutation.mutate(submission);
  };

  return (
    <div className="grid lg:grid-cols-2 gap-8">
      <div>
        <div className="bg-white rounded-xl shadow-lg p-6">
          <h1 className="text-2xl font-bold text-[#232f3e] mb-2">
            🎉 Share Your AWS Certification
          </h1>
          <p className="text-gray-600 mb-6">
            Congratulations on your achievement! Fill out the form below and we'll announce it
            across our community channels.
          </p>

          {mutation.isError && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
              <p className="font-medium">Submission failed</p>
              <p className="text-sm">
                {mutation.error instanceof Error
                  ? mutation.error.message
                  : 'Please try again later.'}
              </p>
            </div>
          )}

          <CertificationForm
            onSubmit={handleSubmit}
            onChange={setFormData}
            isSubmitting={mutation.isPending}
          />
        </div>
      </div>

      <div>
        <div className="sticky top-8">
          <h2 className="text-lg font-semibold text-gray-700 mb-4">📱 Post Previews</h2>
          <PostPreview submission={formData} />
        </div>
      </div>
    </div>
  );
}
