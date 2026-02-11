import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { CheckCircle, Clock, XCircle, ExternalLink, ArrowLeft, RefreshCw } from 'lucide-react';
import { getSubmissionStatus } from '../api/client';
import type { ChannelDelivery } from '../types/certification';

const STATUS_CONFIG = {
  pending: { icon: Clock, color: 'text-yellow-500', bg: 'bg-yellow-50', label: 'Pending' },
  delivered: { icon: CheckCircle, color: 'text-green-500', bg: 'bg-green-50', label: 'Delivered' },
  failed: { icon: XCircle, color: 'text-red-500', bg: 'bg-red-50', label: 'Failed' },
};

const CHANNEL_NAMES: Record<string, string> = {
  facebook: 'Facebook',
  instagram: 'Instagram',
  linkedin: 'LinkedIn',
  whatsapp: 'WhatsApp',
};

function DeliveryStatus({ delivery }: { delivery: ChannelDelivery }) {
  const config = STATUS_CONFIG[delivery.status];
  const Icon = config.icon;

  return (
    <div className={`${config.bg} rounded-lg p-4 flex items-center justify-between`}>
      <div className="flex items-center gap-3">
        <Icon className={`h-6 w-6 ${config.color}`} />
        <div>
          <p className="font-medium text-gray-900">{CHANNEL_NAMES[delivery.channel]}</p>
          <p className="text-sm text-gray-600">{config.label}</p>
          {delivery.error && <p className="text-sm text-red-600 mt-1">{delivery.error}</p>}
        </div>
      </div>
      {delivery.externalPostId && (
        <a
          href={`#${delivery.externalPostId}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[#ff9900] hover:text-[#ec7211] flex items-center gap-1"
        >
          <span className="text-sm">View Post</span>
          <ExternalLink className="h-4 w-4" />
        </a>
      )}
    </div>
  );
}

export function SuccessPage() {
  const { id } = useParams<{ id: string }>();

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['submission', id],
    queryFn: () => getSubmissionStatus(id!),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'scheduled' || status === 'processing' ? 3000 : false;
    },
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="bg-white rounded-xl shadow-lg p-8 text-center">
          <div className="animate-spin h-12 w-12 border-4 border-[#ff9900] border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-gray-600">Loading submission status...</p>
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="bg-white rounded-xl shadow-lg p-8 text-center">
          <XCircle className="h-16 w-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Submission Not Found</h1>
          <p className="text-gray-600 mb-6">
            We couldn't find this submission. It may have been removed or the link is incorrect.
          </p>
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-[#ff9900] hover:text-[#ec7211]"
          >
            <ArrowLeft className="h-4 w-4" />
            Submit a new certification
          </Link>
        </div>
      </div>
    );
  }

  const isProcessing = data.status === 'scheduled' || data.status === 'processing';

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-white rounded-xl shadow-lg p-8">
        <div className="text-center mb-8">
          {isProcessing ? (
            <>
              <div className="animate-pulse">
                <Clock className="h-16 w-16 text-[#ff9900] mx-auto mb-4" />
              </div>
              <h1 className="text-2xl font-bold text-gray-900 mb-2">
                🚀 Your Announcement is Being Published!
              </h1>
              <p className="text-gray-600">
                We're posting your certification achievement across the selected channels. This
                usually takes a few seconds.
              </p>
            </>
          ) : data.status === 'delivered' ? (
            <>
              <CheckCircle className="h-16 w-16 text-green-500 mx-auto mb-4" />
              <h1 className="text-2xl font-bold text-gray-900 mb-2">
                🎉 Congratulations! Your Achievement Has Been Announced!
              </h1>
              <p className="text-gray-600">
                Your AWS certification has been shared with our community. Check the delivery
                status below.
              </p>
            </>
          ) : (
            <>
              <XCircle className="h-16 w-16 text-red-500 mx-auto mb-4" />
              <h1 className="text-2xl font-bold text-gray-900 mb-2">
                Some Posts Failed to Deliver
              </h1>
              <p className="text-gray-600">
                We encountered issues posting to some channels. See details below.
              </p>
            </>
          )}
        </div>

        {data.deliveries && data.deliveries.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-700">Delivery Status</h2>
              {isProcessing && (
                <button
                  onClick={() => refetch()}
                  className="text-sm text-[#ff9900] hover:text-[#ec7211] flex items-center gap-1"
                >
                  <RefreshCw className="h-4 w-4" />
                  Refresh
                </button>
              )}
            </div>
            {data.deliveries.map((delivery) => (
              <DeliveryStatus key={delivery.channel} delivery={delivery} />
            ))}
          </div>
        )}

        <div className="mt-8 pt-6 border-t border-gray-200 text-center">
          <Link
            to="/"
            className="inline-flex items-center gap-2 px-6 py-3 bg-[#232f3e] hover:bg-[#374151] text-white rounded-lg transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Submit Another Certification
          </Link>
        </div>
      </div>
    </div>
  );
}
