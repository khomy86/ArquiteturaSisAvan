import React, { useState, useEffect, useCallback } from 'react';
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
  Tooltip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  TextField
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import DeleteForeverIcon from '@mui/icons-material/DeleteForever';

// Use environment variable or default
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost/api';

// --- Edit Video Dialog Component --- 
const EditVideoDialog = ({ open, onClose, video, onSave }) => {
  const [formData, setFormData] = useState({ title: '', description: '' });
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    // Populate form when video data changes (dialog opens)
    if (video) {
      setFormData({
        title: video.title || '',
        description: video.description || ''
      });
    }
  }, [video]);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    await onSave(video.id, formData); // Call parent save function
    setIsSaving(false);
  };

  if (!video) return null; // Don't render if no video selected

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Edit Video: {video.title} (ID: {video.id})</DialogTitle>
      <DialogContent>
        <DialogContentText sx={{ mb: 2 }}>
          Modify the title and description for this video.
        </DialogContentText>
        <TextField
          autoFocus
          required
          margin="dense"
          id="title"
          name="title"
          label="Video Title"
          type="text"
          fullWidth
          variant="standard"
          value={formData.title}
          onChange={handleChange}
          disabled={isSaving}
        />
        <TextField
          margin="dense"
          id="description"
          name="description"
          label="Video Description"
          type="text"
          fullWidth
          multiline
          rows={4}
          variant="standard"
          value={formData.description}
          onChange={handleChange}
          disabled={isSaving}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isSaving}>Cancel</Button>
        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving ? <CircularProgress size={24} /> : 'Save'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
// --- End Edit Video Dialog Component ---

// Video List Component
const AdminVideoList = () => {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // State for edit dialog
  const [editOpen, setEditOpen] = useState(false);
  const [editingVideo, setEditingVideo] = useState(null);

  // Wrap fetchVideos in useCallback to prevent unnecessary re-renders if passed as prop
  const fetchVideos = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get(`${API_BASE_URL}/videos?include_deleted=true`);
      setVideos(response.data);
    } catch (err) {
      console.error('Error fetching videos:', err);
      setError('Failed to fetch videos. Please try again later.');
    } finally {
      setLoading(false);
    }
  }, []); // Empty dependency array means this function is created once

  useEffect(() => {
    fetchVideos();
  }, [fetchVideos]); // fetchVideos is now stable

  const handleEdit = (video) => {
    setEditingVideo(video); // Set the video to edit
    setEditOpen(true);      // Open the dialog
  };

  const handleCloseEdit = () => {
    setEditOpen(false);
    setEditingVideo(null); // Clear the video being edited
  };

  const handleSaveEdit = async (videoId, updatedData) => {
    setError(null); // Clear previous errors
    try {
      await axios.put(`${API_BASE_URL}/videos/${videoId}`, updatedData);
      handleCloseEdit(); // Close dialog on success
      await fetchVideos(); // Refresh the list
      // TODO: Add success notification (Snackbar)
    } catch (err) {
        console.error('Error updating video:', err);
        // Display error to the user (e.g., in the dialog or via Snackbar)
        alert('Failed to update video. Check console for details.'); 
        setError('Failed to update video.'); // Keep error state for table view if needed
        // Keep dialog open on error? Or handle differently.
    }
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

  const handleDeletePermanently = async (videoId) => {
    if (window.confirm(`Are you sure you want to permanently delete video ID: ${videoId}? This action cannot be undone.`)) {
      setLoading(true);
      try {
        await axios.delete(`${API_BASE_URL}/videos/${videoId}?permanent=true`);
        await fetchVideos(); // Refresh list
      } catch (err) {
        console.error('Error permanently deleting video:', err);
        setError('Failed to permanently delete video. Please try again.');
        setLoading(false); // Ensure loading is stopped on error
      }
      // fetchVideos will set loading to false on success
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
    <>
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
                        onClick={() => handleEdit(video)}
                        disabled={video.is_deleted}
                        size="small"
                      >
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </span>
                  </Tooltip>
                  {video.is_deleted ? (
                    <>
                      <Tooltip title="Delete Forever">
                        <span>
                          <IconButton
                            onClick={() => handleDeletePermanently(video.id)}
                            color="error"
                            size="small"
                          >
                            <DeleteForeverIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                    </>
                  ) : (
                    <Tooltip title="Delete">
                      <span>
                        <IconButton
                          onClick={() => handleDelete(video.id)}
                          color="error"
                          size="small"
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </span>
                    </Tooltip>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Edit Dialog */} 
      <EditVideoDialog
        open={editOpen}
        onClose={handleCloseEdit}
        video={editingVideo}
        onSave={handleSaveEdit}
      />
    </>
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