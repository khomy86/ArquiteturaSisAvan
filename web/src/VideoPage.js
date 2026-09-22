import { useEffect, useRef, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import { Alert, Box, Button, CircularProgress, Typography } from '@mui/material';
import { api, errorMessage } from './api';

export default function VideoPage({ lastChange }) {
  const { videoId } = useParams();
  const [video, setVideo] = useState(null);
  const [error, setError] = useState(null);
  // Bumped whenever the server says this video changed, to trigger a refetch.
  const [version, setVersion] = useState(0);
  const handledChange = useRef(lastChange);

  useEffect(() => {
    if (lastChange === handledChange.current) return;
    handledChange.current = lastChange;
    if (lastChange.action === 'resync' || String(lastChange.video_id) === videoId) {
      setVersion((v) => v + 1);
    }
  }, [lastChange, videoId]);

  useEffect(() => {
    setVideo(null);
    setError(null);
  }, [videoId]);

  // Refetching keeps the current <video> element, so an edit doesn't interrupt
  // playback, while a delete swaps the player for a message.
  useEffect(() => {
    let cancelled = false;
    api
      .get(`/videos/${videoId}`)
      .then(({ data }) => {
        if (cancelled) return;
        setVideo(data);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(
          err.response?.status === 404
            ? 'This video is not available.'
            : errorMessage(err, 'Could not load this video.')
        );
      });
    return () => {
      cancelled = true;
    };
  }, [videoId, version]);

  const backButton = (
    <Button component={RouterLink} to="/" variant="outlined" sx={{ mt: 3 }}>
      Back to videos
    </Button>
  );

  if (error) {
    return (
      <Box sx={{ maxWidth: 900, mx: 'auto' }}>
        <Alert severity="error">{error}</Alert>
        {backButton}
      </Box>
    );
  }

  if (!video) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ maxWidth: 900, mx: 'auto' }}>
      <Box
        component="video"
        src={video.url}
        poster={video.thumbnail_url || undefined}
        controls
        autoPlay
        sx={{ width: '100%', borderRadius: 1, bgcolor: 'common.black' }}
      />
      <Typography variant="h4" sx={{ mt: 2 }}>
        {video.title}
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mt: 1, whiteSpace: 'pre-line' }}>
        {video.description}
      </Typography>
      {backButton}
    </Box>
  );
}
