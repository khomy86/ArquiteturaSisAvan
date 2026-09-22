import { useState } from 'react';
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  LinearProgress,
  TextField,
  Typography,
} from '@mui/material';
import { api, errorMessage } from './api';

const EMPTY_FORM = { title: '', description: '', file: null };

export default function UploadDialog({ open, onClose, onUploaded }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState(null);
  const uploading = progress !== null;

  const close = () => {
    if (uploading) return;
    setForm(EMPTY_FORM);
    setError(null);
    onClose();
  };

  const submit = async (event) => {
    event.preventDefault();
    const body = new FormData();
    body.append('title', form.title);
    body.append('description', form.description);
    body.append('file', form.file);

    setError(null);
    setProgress(0);
    try {
      const { data } = await api.post('/videos/upload', body, {
        onUploadProgress: (e) => e.total && setProgress(Math.round((e.loaded / e.total) * 100)),
      });
      setProgress(null);
      setForm(EMPTY_FORM);
      onUploaded(data);
    } catch (err) {
      setProgress(null);
      setError(errorMessage(err, 'The upload failed.'));
    }
  };

  return (
    <Dialog open={open} onClose={close} fullWidth maxWidth="sm">
      <form onSubmit={submit}>
        <DialogTitle>Upload a video</DialogTitle>
        <DialogContent>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          <TextField
            label="Title"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            inputProps={{ maxLength: 200 }}
            required
            autoFocus
            fullWidth
            margin="dense"
            disabled={uploading}
          />
          <TextField
            label="Description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            multiline
            rows={3}
            fullWidth
            margin="dense"
            disabled={uploading}
          />
          <Button variant="outlined" component="label" sx={{ mt: 2 }} disabled={uploading}>
            Choose file
            <input
              type="file"
              accept="video/*"
              hidden
              onChange={(e) => setForm({ ...form, file: e.target.files[0] || null })}
            />
          </Button>
          {form.file && (
            <Typography variant="body2" sx={{ mt: 1 }}>
              {form.file.name}
            </Typography>
          )}
          {uploading && <LinearProgress variant="determinate" value={progress} sx={{ mt: 2 }} />}
        </DialogContent>
        <DialogActions>
          <Button onClick={close} disabled={uploading}>
            Cancel
          </Button>
          <Button type="submit" variant="contained" disabled={uploading || !form.file || !form.title.trim()}>
            Upload
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
