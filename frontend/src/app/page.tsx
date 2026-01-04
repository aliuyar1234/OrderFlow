import { redirect } from 'next/navigation'

/**
 * Root page - redirects to inbox dashboard
 */
export default function HomePage() {
  redirect('/inbox')
}
