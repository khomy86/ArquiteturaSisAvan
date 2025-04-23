import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  Typography,
  Container,
  Grid,
  Card,
  CardContent,
  CardMedia,
  Button,
  Box,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  LinearProgress,
  Snackbar,
  Alert,
} from '@mui/material';
import ReactPlayer from 'react-player';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';
const STREAMING_BASE_URL = 'http://localhost:8001';

function App() {
  const [videos, setVideos] = useState([]);
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'info' });

  const [newVideo, setNewVideo] = useState({
    title: '',
    description: '',
    file: null
  });

  useEffect(() => {
    fetchVideos();
  }, []);

  const fetchVideos = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/videos`);
      setVideos(response.data);
    } catch (error) {
      console.error('Error fetching videos:', error);
    }
  };

  const handleUpload = async () => {
    if (!newVideo.file || !newVideo.title) {
      setSnackbar({
        open: true,
        message: 'Please fill in all fields and select a file',
        severity: 'error'
      });
      return;
    }

    const formData = new FormData();
    formData.append('file', newVideo.file);
    formData.append('title', newVideo.title);
    formData.append('description', newVideo.description);

    try {
      const response = await axios.post(`${API_BASE_URL}/videos/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      setUploadStatus(response.data);
      setUploadDialogOpen(false);
      setNewVideo({ title: '', description: '', file: null });
      
      // Start polling for upload status
      pollUploadStatus(response.data.upload_id);
    } catch (error) {
      setSnackbar({
        open: true,
        message: 'Error uploading video',
        severity: 'error'
      });
    }
  };

  const pollUploadStatus = async (uploadId) => {
    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/uploads/${uploadId}/status`);
        const status = response.data.status;
        
        if (status === 'completed') {
          clearInterval(interval);
          setUploadProgress(100);
          setSnackbar({
            open: true,
            message: 'Video uploaded successfully',
            severity: 'success'
          });
          fetchVideos(); // Refresh video list
        } else if (status === 'failed') {
          clearInterval(interval);
          setSnackbar({
            open: true,
            message: 'Video upload failed',
            severity: 'error'
          });
        } else if (status === 'processing') {
          setUploadProgress(50);
        }
      } catch (error) {
        clearInterval(interval);
        setSnackbar({
          open: true,
          message: 'Error checking upload status',
          severity: 'error'
        });
      }
    }, 2000);
  };

  const VideoList = () => (
    <Grid container spacing={3}>
      {videos.map((video) => (
        <Grid item xs={12} sm={6} md={4} key={video.id}>
          <Card>
            <CardMedia
              component="img"
              height="140"
              image={`https://img.youtube.com/vi/${video.url.split('v=')[1]}/hqdefault.jpg`}
              alt={video.title}
            />
            <CardContent>
              <Typography gutterBottom variant="h5" component="div">
                {video.title}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {video.description}
              </Typography>
              <Button
                size="small"
                color="primary"
                onClick={() => setSelectedVideo(video)}
                sx={{ mt: 2 }}
              >
                Watch Video
              </Button>
            </CardContent>
          </Card>
        </Grid>
      ))}
    </Grid>
  );

  const VideoPlayer = () => (
    <Box sx={{ width: '100%', maxWidth: 800, mx: 'auto', mt: 4 }}>
      {selectedVideo && (
        <>
          <Typography variant="h4" gutterBottom>
            {selectedVideo.title}
          </Typography>
          <ReactPlayer
            url={selectedVideo.url}
            controls
            width="100%"
            height="auto"
          />
          <Typography variant="body1" sx={{ mt: 2 }}>
            {selectedVideo.description}
          </Typography>
          <Button
            variant="contained"
            onClick={() => setSelectedVideo(null)}
            sx={{ mt: 2 }}
          >
            Back to Videos
          </Button>
        </>
      )}
    </Box>
  );

  return (
    <Router>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            UALFlix
          </Typography>
          <Button color="inherit" onClick={() => setUploadDialogOpen(true)}>
            Upload Video
          </Button>
        </Toolbar>
      </AppBar>

      <Container sx={{ py: 4 }}>
        {uploadProgress > 0 && uploadProgress < 100 && (
          <Box sx={{ width: '100%', mb: 2 }}>
            <LinearProgress variant="determinate" value={uploadProgress} />
          </Box>
        )}

        <Routes>
          <Route
            path="/"
            element={
              selectedVideo ? (
                <VideoPlayer />
              ) : (
                <VideoList />
              )
            }
          />
        </Routes>
      </Container>

      <Dialog open={uploadDialogOpen} onClose={() => setUploadDialogOpen(false)}>
        <DialogTitle>Upload New Video</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Title"
            fullWidth
            value={newVideo.title}
            onChange={(e) => setNewVideo({ ...newVideo, title: e.target.value })}
          />
          <TextField
            margin="dense"
            label="Description"
            fullWidth
            multiline
            rows={4}
            value={newVideo.description}
            onChange={(e) => setNewVideo({ ...newVideo, description: e.target.value })}
          />
          <Button
            variant="contained"
            component="label"
            sx={{ mt: 2 }}
          >
            Select Video File
            <input
              type="file"
              hidden
              accept="video/*"
              onChange={(e) => setNewVideo({ ...newVideo, file: e.target.files[0] })}
            />
          </Button>
          {newVideo.file && (
            <Typography variant="body2" sx={{ mt: 1 }}>
              Selected: {newVideo.file.name}
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setUploadDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleUpload}>Upload</Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          severity={snackbar.severity}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Router>
  );
}

export default App; 