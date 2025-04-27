import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import {
  CssBaseline,
  AppBar,
  Toolbar,
  Typography,
  Container,
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Button,
  CircularProgress,
  Alert,
  IconButton,
  Tooltip
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';

// Use environment variable or default
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost/api';

// Video List Component
const AdminVideoList = () => {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchVideos = async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch all videos, including deleted ones
      const response = await axios.get(`${API_BASE_URL}/videos?include_deleted=true`);
      setVideos(response.data);
    } catch (err) {
      console.error('Error fetching videos:', err);
      setError('Failed to fetch videos. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVideos();
  }, []);

  const handleEdit = (videoId) => {
    // TODO: Implement navigation or modal for editing
    console.log('Edit video:', videoId);
    alert(`Edit action for video ID: ${videoId} (Not Implemented)`);
  };

  const handleDelete = async (videoId) => {
    // Confirm before deleting
    if (window.confirm(`Are you sure you want to delete video ID: ${videoId}? This will also remove the video file and thumbnail from storage.`)) {
        setLoading(true); // Optional: Show loading indicator during delete
        try {
            await axios.delete(`${API_BASE_URL}/videos/${videoId}`);
            await fetchVideos(); // Refresh list after delete
            // Optional: Add success snackbar/message
        } catch (err) {
            console.error('Error deleting video:', err);
            setError('Failed to delete video. Please try again.');
            setLoading(false);
        }
        // No finally setLoading(false) here, as fetchVideos handles it
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error" sx={{ mt: 4 }}>{error}</Alert>;
  }

  return (
    <TableContainer component={Paper} sx={{ mt: 4 }}>
      <Table sx={{ minWidth: 650 }} aria-label="admin video table">
        <TableHead>
          <TableRow>
            <TableCell>ID</TableCell>
            <TableCell>Title</TableCell>
            <TableCell>Description</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Deleted?</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {videos.map((video) => (
            <TableRow
              key={video.id}
              sx={{ 
                '&:last-child td, &:last-child th': { border: 0 },
                backgroundColor: video.is_deleted ? '#ffebee' : 'inherit' // Highlight deleted rows
              }}
            >
              <TableCell component="th" scope="row">
                {video.id}
              </TableCell>
              <TableCell>{video.title}</TableCell>
              <TableCell>{video.description?.substring(0, 50)}{video.description?.length > 50 ? '...' : ''}</TableCell>
              <TableCell>{video.status}</TableCell>
              <TableCell>{video.is_deleted ? 'Yes' : 'No'}</TableCell>
              <TableCell align="right">
                <Tooltip title="Edit">
                  <span>
                    <IconButton 
                      onClick={() => handleEdit(video.id)} 
                      disabled={video.is_deleted} // Disable edit for deleted videos
                      size="small"
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </span>
                </Tooltip>
                <Tooltip title={video.is_deleted ? "Restore (Not Implemented)" : "Delete"}>
                   <span>
                    <IconButton 
                      onClick={() => handleDelete(video.id)} 
                      color={video.is_deleted ? "default" : "error"}
                      size="small"
                    >
                      {/* TODO: Change icon/action for restoring */} 
                      <DeleteIcon fontSize="small" /> 
                    </IconButton>
                  </span>
                </Tooltip>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

function App() {
  return (
    <Router basename="/admin"> {/* Set base path for routing */}
      <CssBaseline />
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6">UALFlix Admin</Typography>
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg"> {/* Use a wider container */}
        <Box component="main" sx={{ flexGrow: 1, py: 3 }}>
            <Typography variant="h4" gutterBottom>Admin Video Management</Typography>
            <Routes>
            <Route path="/" element={<AdminVideoList />} />
            {/* Add routes for editing later */}
            </Routes>
        </Box>
      </Container>
    </Router>
  );
}

export default App; 