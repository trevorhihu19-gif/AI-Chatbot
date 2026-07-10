import { SignedIn, SignedOut, RedirectToSignIn } from '@clerk/clerk-react'
import AppLayout from './components/layout/AppLayout'

function App() {
  return (
    <>
      <SignedOut>
        <RedirectToSignIn />
      </SignedOut>
      <SignedIn>
        <AppLayout>
          <div className="flex items-center justify-center h-full text-[#555]">
            Chat area coming soon
          </div>
        </AppLayout>
      </SignedIn>
    </>
  )
}

export default App