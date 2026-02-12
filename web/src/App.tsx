import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/Layout';
import { SubmitPage } from './pages/SubmitPage';
import { SuccessPage } from './pages/SuccessPage';
import { QuickPublishPage } from './pages/QuickPublishPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5000,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<SubmitPage />} />
            <Route path="publish" element={<QuickPublishPage />} />
            <Route path="success/:id" element={<SuccessPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
