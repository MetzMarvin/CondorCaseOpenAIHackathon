import React from 'react';
import { createRoot } from 'react-dom/client';
// Keep customer and operator views, including their styles, separate.
const portal = window.location.pathname === '/portal' || window.location.pathname.startsWith('/portal/');
const component = portal
  ? import('./portal/CustomerPortal.jsx')
  : Promise.all([import('./App.jsx'), import('./style.css')]).then(([module]) => module);
component.then(({ default: View }) => createRoot(document.getElementById('root')).render(<View />));
