import { useEffect, useState } from 'react';
import {
  AppBar,
  Box,
  Button,
  CircularProgress,
  Container,
  CssBaseline,
  Toolbar,
  Typography,
} from '@mui/material';
import LogoutIcon from '@mui/icons-material/Logout';
import { api, clearToken, getToken, onUnauthorized } from './api';
import LoginPage from './LoginPage';
import VideoTable from './VideoTable';

export default function App() {
  const [user, setUser] = useState(null);
  // Only show the spinner if there's a stored token worth checking.
  const [checking, setChecking] = useState(Boolean(getToken()));

  useEffect(() => {
    onUnauthorized(() => setUser(null));
    if (!getToken()) return;
    api
      .get('/auth/me')
      .then(({ data }) => setUser(data))
      .catch(() => clearToken())
      .finally(() => setChecking(false));
  }, []);

  const logout = () => {
    clearToken();
    setUser(null);
  };

  let content;
  if (checking) {
    content = (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 10 }}>
        <CircularProgress />
      </Box>
    );
  } else if (!user) {
    content = <LoginPage onLogin={setUser} />;
  } else {
    content = (
      <>
        <AppBar position="static">
          <Toolbar>
            <Typography variant="h6" sx={{ flexGrow: 1 }}>
              UALFlix Admin
            </Typography>
            <Typography variant="body2" sx={{ mr: 2 }}>
              {user.username}
            </Typography>
            <Button color="inherit" startIcon={<LogoutIcon />} onClick={logout}>
              Sign out
            </Button>
          </Toolbar>
        </AppBar>
        <Container maxWidth="lg" sx={{ py: 4 }}>
          <VideoTable />
        </Container>
      </>
    );
  }

  return (
    <>
      <CssBaseline />
      {content}
    </>
  );
}
