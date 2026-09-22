import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Avatar,
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  Paper,
  Snackbar,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import DeleteForeverIcon from '@mui/icons-material/DeleteForever';
import EditIcon from '@mui/icons-material/Edit';
import RefreshIcon from '@mui/icons-material/Refresh';
import RestoreFromTrashIcon from '@mui/icons-material/RestoreFromTrash';
import { api, errorMessage, subscribeToCatalog } from './api';
import EditVideoDialog from './EditVideoDialog';

const STATUS_COLORS = {
  completed: 'success',
  processing: 'info',
  pending: 'default',
  failed: 'error',
};

function ActionButton({ title, onClick, color, children }) {
  return (
    <Tooltip title={title}>
      <IconButton size="small" color={color} onClick={onClick} aria-label={title}>
        {children}
      </IconButton>
    </Tooltip>
  );
}

export default function VideoTable() {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [notice, setNotice] = useState(null);

  const showError = (err, fallback) =>
    setNotice({ severity: 'error', message: errorMessage(err, fallback) });

  const load = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true);
    try {
      const { data } = await api.get('/admin/videos');
      setVideos(data);
    } catch (err) {
      showError(err, 'Could not load videos.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Live status updates, e.g. an upload moving from pending to completed.
  useEffect(() => subscribeToCatalog(() => load({ quiet: true })), [load]);

  const replace = (updated) =>
    setVideos((list) => list.map((v) => (v.id === updated.id ? updated : v)));

  const save = async (id, changes) => {
    try {
      const { data } = await api.patch(`/admin/videos/${id}`, changes);
      replace(data);
      setEditing(null);
      setNotice({ severity: 'success', message: 'Video updated.' });
    } catch (err) {
      showError(err, 'Could not save the changes.');
    }
  };

  const softDelete = async (video) => {
    try {
      await api.delete(`/admin/videos/${video.id}`);
      replace({ ...video, is_deleted: true });
      setNotice({ severity: 'success', message: `"${video.title}" is hidden. You can restore it.` });
    } catch (err) {
      showError(err, 'Could not delete the video.');
    }
  };

  const restore = async (video) => {
    try {
      const { data } = await api.post(`/admin/videos/${video.id}/restore`);
      replace(data);
      setNotice({ severity: 'success', message: `"${video.title}" restored.` });
    } catch (err) {
      showError(err, 'Could not restore the video.');
    }
  };

  const deleteForever = async (video) => {
    if (!window.confirm(`Permanently delete "${video.title}" and its files? This cannot be undone.`)) {
      return;
    }
    try {
      await api.delete(`/admin/videos/${video.id}`, { params: { permanent: true } });
      setVideos((list) => list.filter((v) => v.id !== video.id));
      setNotice({ severity: 'success', message: `"${video.title}" deleted.` });
    } catch (err) {
      showError(err, 'Could not delete the video.');
    }
  };

  return (
    <>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5" sx={{ flexGrow: 1 }}>
          Videos
        </Typography>
        <Button startIcon={<RefreshIcon />} onClick={() => load()} disabled={loading}>
          Refresh
        </Button>
      </Box>

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell />
              <TableCell>Title</TableCell>
              <TableCell>Description</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Uploaded</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading && videos.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 4 }}>
                  <CircularProgress size={28} />
                </TableCell>
              </TableRow>
            )}
            {!loading && videos.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                  No videos have been uploaded yet.
                </TableCell>
              </TableRow>
            )}
            {videos.map((video) => (
              <TableRow key={video.id} sx={{ opacity: video.is_deleted ? 0.55 : 1 }}>
                <TableCell>{video.id}</TableCell>
                <TableCell>
                  <Avatar variant="rounded" src={video.thumbnail_url || undefined} sx={{ width: 64, height: 36 }}>
                    {' '}
                  </Avatar>
                </TableCell>
                <TableCell>{video.title}</TableCell>
                <TableCell sx={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {video.description}
                </TableCell>
                <TableCell>
                  {video.is_deleted ? (
                    <Chip size="small" label="deleted" variant="outlined" />
                  ) : (
                    <Chip size="small" label={video.status} color={STATUS_COLORS[video.status] || 'default'} />
                  )}
                </TableCell>
                <TableCell>{new Date(video.created_at).toLocaleString()}</TableCell>
                <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                  {video.is_deleted ? (
                    <>
                      <ActionButton title="Restore" onClick={() => restore(video)}>
                        <RestoreFromTrashIcon fontSize="small" />
                      </ActionButton>
                      <ActionButton title="Delete forever" color="error" onClick={() => deleteForever(video)}>
                        <DeleteForeverIcon fontSize="small" />
                      </ActionButton>
                    </>
                  ) : (
                    <>
                      <ActionButton title="Edit" onClick={() => setEditing(video)}>
                        <EditIcon fontSize="small" />
                      </ActionButton>
                      <ActionButton title="Delete" color="error" onClick={() => softDelete(video)}>
                        <DeleteIcon fontSize="small" />
                      </ActionButton>
                    </>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <EditVideoDialog video={editing} onClose={() => setEditing(null)} onSave={save} />

      <Snackbar
        open={Boolean(notice)}
        autoHideDuration={5000}
        onClose={(_e, reason) => reason !== 'clickaway' && setNotice(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Box>
          {notice && (
            <Alert severity={notice.severity} variant="filled" onClose={() => setNotice(null)}>
              {notice.message}
            </Alert>
          )}
        </Box>
      </Snackbar>
    </>
  );
}
