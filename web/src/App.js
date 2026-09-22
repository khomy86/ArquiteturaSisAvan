import { useCallback, useEffect, useRef, useState } from 'react';
import { BrowserRouter, Link as RouterLink, Route, Routes, useMatch } from 'react-router-dom';
import {
  Alert,
  AppBar,
  Box,
  Button,
  Container,
  CssBaseline,
  Snackbar,
  Toolbar,
  Typography,
} from '@mui/material';
import { api, errorMessage, subscribeToCatalog } from './api';
import UploadDialog from './UploadDialog';
import VideoGrid from './VideoGrid';
import VideoPage from './VideoPage';

const POLL_INTERVAL_MS = 2000;

function Shell() {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [notice, setNotice] = useState(null);
  const [lastChange, setLastChange] = useState(null);
  const pollers = useRef(new Set());
  const onVideoPage = useMatch('/video/:videoId');

  const loadVideos = useCallback(async () => {
    try {
      const { data } = await api.get('/videos');
      setVideos(data);
    } catch (err) {
      setNotice({ severity: 'error', message: errorMessage(err, 'Could not load videos.') });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadVideos();
    const active = pollers.current;
    return () => active.forEach(clearInterval);
  }, [loadVideos]);

  // Keep the list in sync when videos are processed, edited, deleted or
  // restored anywhere else, e.g. from the admin panel.
  useEffect(
    () =>
      subscribeToCatalog((change) => {
        loadVideos();
        setLastChange(change);
      }),
    [loadVideos]
  );

  const watchUpload = (uploadId, title) => {
    const timer = setInterval(async () => {
      let status;
      try {
        ({ data: status } = await api.get(`/uploads/${uploadId}/status`));
      } catch {
        return; // try again on the next tick
      }
      if (status.status === 'completed' || status.status === 'failed') {
        clearInterval(timer);
        pollers.current.delete(timer);
      }
      if (status.status === 'completed') {
        setNotice({ severity: 'success', message: `"${title}" is ready to watch.` });
        loadVideos();
      } else if (status.status === 'failed') {
        setNotice({ severity: 'error', message: status.error || `Processing "${title}" failed.` });
      }
    }, POLL_INTERVAL_MS);
    pollers.current.add(timer);
  };

  const handleUploaded = ({ upload_id, video }) => {
    setUploadOpen(false);
    setNotice({ severity: 'info', message: `Uploaded "${video.title}". Processing...` });
    watchUpload(upload_id, video.title);
  };

  const closeNotice = (_event, reason) => {
    if (reason !== 'clickaway') setNotice(null);
  };

  return (
    <>
      <AppBar position="static">
        <Toolbar>
          <Typography
            variant="h6"
            component={RouterLink}
            to="/"
            sx={{ flexGrow: 1, color: 'inherit', textDecoration: 'none' }}
          >
            UALFlix
          </Typography>
          <Button color="inherit" onClick={() => setUploadOpen(true)} disabled={Boolean(onVideoPage)}>
            Upload video
          </Button>
        </Toolbar>
      </AppBar>

      <Container sx={{ py: 4 }}>
        <Routes>
          <Route path="/" element={<VideoGrid videos={videos} loading={loading} />} />
          <Route path="/video/:videoId" element={<VideoPage lastChange={lastChange} />} />
        </Routes>
      </Container>

      <UploadDialog open={uploadOpen} onClose={() => setUploadOpen(false)} onUploaded={handleUploaded} />

      <Snackbar
        open={Boolean(notice)}
        autoHideDuration={6000}
        onClose={closeNotice}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Box>
          {notice && (
            <Alert onClose={closeNotice} severity={notice.severity} variant="filled">
              {notice.message}
            </Alert>
          )}
        </Box>
      </Snackbar>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <CssBaseline />
      <Shell />
    </BrowserRouter>
  );
}
