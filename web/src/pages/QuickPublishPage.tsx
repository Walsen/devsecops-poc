import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  Send,
  Facebook,
  Instagram,
  Linkedin,
  MessageCircle,
  CheckCircle,
  AlertCircle,
} from 'lucide-react';
import { scheduleMessage } from '../api/client';

type Channel = 'facebook' | 'instagram' | 'linkedin' | 'whatsapp';

const CHANNELS: { id: Channel; name: string; icon: React.ReactNode; color: string }[] = [
  { id: 'facebook', name: 'Facebook', icon: <Facebook className="h-5 w-5" />, color: 'bg-[#1877f2]' },
  { id: 'instagram', name: 'Instagram', icon: <Instagram className="h-5 w-5" />, color: 'bg-gradient-to-r from-[#833ab4] via-[#fd1d1d] to-[#fcb045]' },
  { id: 'linkedin', name: 'LinkedIn', icon: <Linkedin className="h-5 w-5" />, color: 'bg-[#0a66c2]' },
  { id: 'whatsapp', name: 'WhatsApp', icon: <MessageCircle className="h-5 w-5" />, color: 'bg-[#25d366]' },
];

export function QuickPublishPage() {
  const [content, setContent] = useState('');
  const [selectedChannels, setSelectedChannels] = useState<Channel[]>([]);

  const mutation = useMutation({
    mutationFn: scheduleMessage,
    onSuccess: () => {
      setContent('');
      setSelectedChannels([]);
    },
  });

  const toggleChannel = (channel: Channel) => {
    setSelectedChannels((prev) =>
      prev.includes(channel) ? prev.filter((c) => c !== channel) : [...prev, channel]
    );
  };

  const selectAll = () => {
    setSelectedChannels(
      selectedChannels.length === CHANNELS.length ? [] : CHANNELS.map((c) => c.id)
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim() || selectedChannels.length === 0) return;
    mutation.mutate({ content: content.trim(), channels: selectedChannels });
  };

  const charCount = content.length;
  const maxChars = 280;

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-white rounded-xl shadow-lg p-6">
        <h1 className="text-2xl font-bold text-[#232f3e] mb-2">
          📢 Quick Publish
        </h1>
        <p className="text-gray-600 mb-6">
          Send a message to your social channels. Pick the channels and type your message.
        </p>

        {mutation.isSuccess && (
          <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg flex items-center gap-3">
            <CheckCircle className="h-5 w-5 text-green-600 shrink-0" />
            <div>
              <p className="font-medium text-green-800">Message scheduled</p>
              <p className="text-sm text-green-700">
                ID: {mutation.data?.id} — Status: {mutation.data?.status}
              </p>
            </div>
          </div>
        )}

        {mutation.isError && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-red-600 shrink-0" />
            <div>
              <p className="font-medium text-red-800">Failed to send</p>
              <p className="text-sm text-red-700">
                {mutation.error instanceof Error ? mutation.error.message : 'Please try again.'}
              </p>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Channel selection */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">
                Channels *
              </label>
              <button
                type="button"
                onClick={selectAll}
                className="text-xs text-[#0073bb] hover:underline"
              >
                {selectedChannels.length === CHANNELS.length ? 'Deselect all' : 'Select all'}
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {CHANNELS.map((channel) => {
                const selected = selectedChannels.includes(channel.id);
                return (
                  <button
                    key={channel.id}
                    type="button"
                    onClick={() => toggleChannel(channel.id)}
                    className={`flex items-center gap-2 px-4 py-3 rounded-lg border-2 transition-all ${
                      selected
                        ? 'border-[#ff9900] bg-orange-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <span className={`${channel.color} text-white p-1.5 rounded-md`}>
                      {channel.icon}
                    </span>
                    <span className="font-medium text-gray-700">{channel.name}</span>
                    {selected && <CheckCircle className="h-4 w-4 text-[#ff9900] ml-auto" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Message content */}
          <div>
            <label htmlFor="content" className="block text-sm font-medium text-gray-700 mb-1">
              Message *
            </label>
            <textarea
              id="content"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              maxLength={maxChars}
              rows={4}
              placeholder="Type your message here..."
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff9900] focus:border-transparent resize-none"
            />
            <p className={`text-xs mt-1 text-right ${charCount > maxChars * 0.9 ? 'text-orange-600' : 'text-gray-400'}`}>
              {charCount}/{maxChars}
            </p>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={!content.trim() || selectedChannels.length === 0 || mutation.isPending}
            className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-[#ff9900] hover:bg-[#ec7211] disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors"
          >
            {mutation.isPending ? (
              <>
                <div className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full" />
                Sending...
              </>
            ) : (
              <>
                <Send className="h-5 w-5" />
                Publish to {selectedChannels.length} channel{selectedChannels.length !== 1 ? 's' : ''}
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
