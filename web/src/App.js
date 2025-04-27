import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate, useParams, Link as RouterLink } from 'react-router-dom';
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
  Link,
} from '@mui/material';
import ReactPlayer from 'react-player';
import axios from 'axios';

// Use environment variables or default to localhost:80 (load balancer)
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:80/api';
const STREAMING_BASE_URL = process.env.REACT_APP_STREAMING_URL || 'http://localhost:80/stream';

function App() {
  return (
    <Router>
      <AppContent />
    </Router>
  );
}

// Extract main content into a separate component to use hooks like useNavigate
function AppContent() {
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
      setSnackbar({ open: true, message: 'Failed to fetch videos', severity: 'error' });
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

  // VideoList component now uses useNavigate
  const VideoList = ({ videos }) => {
    const navigate = useNavigate();

    return (
      <Grid container spacing={3}>
        {videos.map((video) => (
          <Grid item xs={12} sm={6} md={4} key={video.id}>
            <Card>
              {/* Use the placeholder image */}
              <CardMedia
                component="img" // Change component type to img
                sx={{ height: 140 }} // Keep the height or adjust as needed
                image="/placeholder-thumbnail.png" // Set image source
                alt={`${video.title} thumbnail`} // Add alt text
              />
              <CardContent>
                <Typography gutterBottom variant="h5" component="div">
                  {video.title}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {video.description}
                </Typography>
                {/* Use Button + navigate or Link component */}
                <Button
                  size="small"
                  color="primary"
                  // Navigate to the video player route
                  onClick={() => navigate(`/video/${video.id}`)}
                  sx={{ mt: 2 }}
                >
                  Watch Video
                </Button>
                 {/* Alternative: Using Link */}
                 {/* <Link component={RouterLink} to={`/video/${video.id}`} sx={{ mt: 2, display: 'block' }}>
                   Watch Video (Link)
                 </Link> */}
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    );
  };

  // VideoPlayer component now uses useParams to get videoId
  const VideoPlayer = ({ videos }) => {
    const { videoId } = useParams();
    const navigate = useNavigate();
    // Find the video object from the list based on the ID from the URL
    const selectedVideo = videos.find(v => v.id === parseInt(videoId));

    // Construct the ABSOLUTE video URL pointing to the Nginx proxy (port 80)
    const nginxBaseUrl = 'http://localhost:80'; // Explicitly define the correct base
    const absoluteVideoUrl = selectedVideo ? `${nginxBaseUrl}${selectedVideo.url}` : ''; // Construct correct absolute URL

    if (!selectedVideo) {
       // Handle case where video ID is invalid or videos haven't loaded yet
       return (
         <Box sx={{ textAlign: 'center', mt: 4 }}>
           <Typography>Video not found or still loading...</Typography>
           <Button variant="contained" onClick={() => navigate('/')} sx={{ mt: 2 }}>
              Back to Videos
           </Button>
         </Box>
       );
    }

    return (
      <Box sx={{ width: '100%', maxWidth: 800, mx: 'auto', mt: 4 }}>
          <>
            <Typography variant="h4" gutterBottom>
              {selectedVideo.title}
            </Typography>
            <ReactPlayer
              url={absoluteVideoUrl} // Use the corrected ABSOLUTE URL
              controls
              playing // Optional: attempt to autoplay
              width="100%"
              height="auto"
              onError={(e) => {
                console.error('ReactPlayer Error:', e);
                setSnackbar({ open: true, message: `Error playing video: ${e.type || 'Unknown error'}`, severity: 'error' });
              }}
            />
            <Typography variant="body1" sx={{ mt: 2 }}>
              {selectedVideo.description}
            </Typography>
            <Button
              variant="contained"
              // Navigate back to the home/list route
              onClick={() => navigate('/')}
              sx={{ mt: 2 }}
            >
              Back to Videos
            </Button>
          </>
      </Box>
    );
  };

  const handleCloseSnackbar = (event, reason) => {
      if (reason === 'clickaway') {
        return;
      }
      setSnackbar({ ...snackbar, open: false });
    };

  return (
    <Box sx={{ flexGrow: 1 }}>
       <AppBar position="static">
         <Toolbar>
           {/* Add flexGrow to push the button to the right */}
           <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
             <Link component={RouterLink} to="/" sx={{ color: 'inherit', textDecoration: 'none' }}>
               UALFlix
             </Link>
           </Typography>
           <Button color="inherit" onClick={() => setUploadDialogOpen(true)}>
             Upload Video
           </Button>
         </Toolbar>
       </AppBar>
      <Container sx={{ mt: 4, mb: 4 }}>
         {/* Setup Routes */}
         <Routes>
            {/* Route for the video list (home page) */}
           <Route path="/" element={<VideoList videos={videos} />} />
            {/* Route for the video player */}
           <Route path="/video/:videoId" element={<VideoPlayer videos={videos} />} />
         </Routes>

         {/* Upload Dialog remains the same */}
         <Dialog open={uploadDialogOpen} onClose={() => setUploadDialogOpen(false)}>
           <DialogTitle>Upload New Video</DialogTitle>
           <DialogContent>
              {/* Restore the missing input fields */}
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
              {/* Display upload progress if available */}
               {uploadStatus && uploadProgress > 0 && uploadProgress < 100 && (
                 <Box sx={{ width: '100%', mt: 2 }}>
                   <LinearProgress variant="determinate" value={uploadProgress} />
                 </Box>
               )}
           </DialogContent>
           <DialogActions>
             <Button onClick={() => setUploadDialogOpen(false)}>Cancel</Button>
             <Button onClick={handleUpload}>Upload</Button>
           </DialogActions>
         </Dialog>

         {/* Snackbar for notifications */}
         <Snackbar
           open={snackbar.open}
           autoHideDuration={6000}
           onClose={handleCloseSnackbar}
           anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
          >
           <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
             {snackbar.message}
           </Alert>
         </Snackbar>
      </Container>
    </Box>
  );
}

export default App; 