import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '../components/layout/AppShell.jsx'
import { HomePage } from '../pages/HomePage.jsx'
import { PresentationPage } from '../pages/PresentationPage.jsx'
import { ViewerPage } from '../pages/ViewerPage.jsx'

export function AppRouter() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="/viewer" element={<ViewerPage />} />
        <Route path="/presentation" element={<PresentationPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/viewer" replace />} />
    </Routes>
  )
}
