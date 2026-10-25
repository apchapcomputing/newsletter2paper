import fs from 'node:fs'
import path from 'node:path'
import { Atkinson_Hyperlegible, Courier_Prime, Unbounded, UnifrakturCook } from 'next/font/google'
import './landing.css'
import Shell from './Shell'
import Landing from './Landing'

// The design system's four faces, loaded here until the app migrates to them (branch
// feature/ui-design-flow does the same in app/layout.js). Then the fonts, Shell and the token
// block at the top of landing.css can go. Set up in the page rather than a nested layout.js:
// a nested layout made emotion's inline global <style> mismatch during hydration.
const atkinson = Atkinson_Hyperlegible({ variable: '--font-atkinson', subsets: ['latin'], weight: ['400', '700'], style: ['normal', 'italic'] })
const courier = Courier_Prime({ variable: '--font-courier', subsets: ['latin'], weight: ['400', '700'] })
const unbounded = Unbounded({ variable: '--font-unbounded', subsets: ['latin'], weight: ['600', '700', '800'] })
const unifraktur = UnifrakturCook({ variable: '--font-unifraktur', subsets: ['latin'], weight: '700' })

const title = 'newsletter2paper: the reading you meant to do, on paper'
const description = 'Turn the Substack and RSS newsletters you follow into one printable newspaper or essay PDF. Read offline, annotate, or get it by email on a schedule.'

export const metadata = {
  title,
  description,
  openGraph: { title, description, type: 'website' },
}

// Sample PDFs and photos (hero.*, print-*.* for the feature accordion in order) are dropped into public/ by hand; sections only render for files that exist.
const SAMPLES = [
  { id: 'newspaper', label: 'Newspaper layout', file: 'sample-newspaper.pdf' },
  { id: 'essay', label: 'Essay layout', file: 'sample-essay.pdf' },
]

function publicFiles(dir) {
  try {
    return fs.readdirSync(path.join(process.cwd(), 'public', dir))
  } catch {
    return []
  }
}

export default function WelcomePage() {
  const present = new Set(publicFiles('samples'))
  const samples = SAMPLES.filter((s) => present.has(s.file)).map((s) => ({ ...s, href: `/samples/${s.file}` }))
  const landing = publicFiles('landing')
  const images = (prefix) => landing
    .filter((f) => new RegExp(`^${prefix}.*\\.(jpe?g|png|webp)$`, 'i').test(f))
    .sort()
    .map((f) => `/landing/${f}`)
  const [heroImage = null] = images('hero')
  return (
    <Shell className={`lp ${atkinson.variable} ${courier.variable} ${unbounded.variable} ${unifraktur.variable}`}>
      <Landing samples={samples} photos={images('print-')} heroImage={heroImage} />
    </Shell>
  )
}
