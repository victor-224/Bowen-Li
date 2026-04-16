import { BrowserRouter } from 'react-router-dom'
import { AppRouter } from './app/AppRouter.jsx'

function App() {
  return (
    <BrowserRouter>
      <AppRouter />
    </BrowserRouter>
  )
}

export default App
