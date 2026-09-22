import { Link as RouterLink } from 'react-router-dom';
import {
  Box,
  Card,
  CardActionArea,
  CardContent,
  CardMedia,
  Grid,
  Typography,
} from '@mui/material';
import { formatDuration } from './api';

export default function VideoGrid({ videos, loading }) {
  if (!loading && videos.length === 0) {
    return (
      <Typography color="text.secondary" sx={{ textAlign: 'center', mt: 6 }}>
        No videos yet. Upload one to get started.
      </Typography>
    );
  }

  return (
    <Grid container spacing={3}>
      {videos.map((video) => (
        <Grid item xs={12} sm={6} md={4} key={video.id}>
          <Card>
            <CardActionArea component={RouterLink} to={`/video/${video.id}`}>
              <Box sx={{ position: 'relative' }}>
                <CardMedia
                  component="img"
                  image={video.thumbnail_url || '/placeholder-thumbnail.png'}
                  alt=""
                  sx={{ height: 180, objectFit: 'cover', bgcolor: 'grey.900' }}
                />
                <Typography
                  variant="caption"
                  sx={{
                    position: 'absolute',
                    bottom: 8,
                    right: 8,
                    px: 0.75,
                    borderRadius: 1,
                    color: 'common.white',
                    bgcolor: 'rgba(0, 0, 0, 0.75)',
                  }}
                >
                  {formatDuration(video.duration)}
                </Typography>
              </Box>
              <CardContent>
                <Typography variant="h6" noWrap>
                  {video.title}
                </Typography>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
                    minHeight: '2.86em',
                  }}
                >
                  {video.description}
                </Typography>
              </CardContent>
            </CardActionArea>
          </Card>
        </Grid>
      ))}
    </Grid>
  );
}
