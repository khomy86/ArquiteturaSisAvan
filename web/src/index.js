import React from 'react';
import ReactDOM from 'react-dom/client'; // Use react-dom/client for React 18+
import './index.css'; // Assuming a basic CSS file might be needed/exist later
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
// reportWebVitals(); // You can uncomment this if you have reportWebVitals setup 