import { Link } from 'react-router-dom'
import { GraduationCap, ScanFace, Eye, Brain, Activity, Video, ListChecks } from 'lucide-react'

const models = [
  { icon: ScanFace, name: 'Face Authentication', desc: 'Verifies student identity before monitoring begins.' },
  { icon: Brain, name: 'Emotion Detection', desc: 'CNN-based recognition of facial affect in real time.' },
  { icon: Eye, name: 'Gaze & Head Pose Estimation', desc: 'MediaPipe-based tracking of attention direction.' },
  { icon: Video, name: 'Object Detection', desc: 'YOLO-based detection of phones and unauthorized devices.' },
  { icon: Activity, name: 'Voice Analysis', desc: 'Detects speaking activity and background disturbance.' },
  { icon: ListChecks, name: 'LSTM Engagement Prediction', desc: 'Forecasts attention drops from engagement history.' },
]

export function AboutPage() {
  return (
    <div className="min-h-screen bg-bg-light dark:bg-bg-dark">
      <header className="mx-auto flex max-w-4xl items-center gap-2 px-6 py-6">
        <Link to="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-focus-500 text-white"><GraduationCap className="h-4 w-4" /></div>
          <span className="font-display text-sm font-bold text-text-light dark:text-text-dark">Cognivue</span>
        </Link>
      </header>

      <div className="mx-auto max-w-4xl px-6 pb-20">
        <h1 className="font-display text-3xl font-bold text-text-light dark:text-text-dark">About Cognivue</h1>
        <p className="mt-3 max-w-2xl text-textmuted-light dark:text-textmuted-dark">
          Cognivue is a Predictive Multimodal Student Engagement and Cognitive Monitoring System, developed as a final-year
          engineering project at the Dept. of Computer Science &amp; Engineering, BIT. It brings AI-driven attentiveness
          insight to virtual classrooms — something teachers have in physical classrooms but lose entirely online.
        </p>

        <h2 className="mt-10 font-display text-xl font-semibold text-text-light dark:text-text-dark">The six models behind the platform</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {models.map((m) => (
            <div key={m.name} className="rounded-2xl border border-border-light p-4 dark:border-border-dark">
              <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-lg bg-focus-500/10"><m.icon className="h-4.5 w-4.5 text-focus-500" /></div>
              <p className="text-sm font-semibold text-text-light dark:text-text-dark">{m.name}</p>
              <p className="mt-1 text-sm text-textmuted-light dark:text-textmuted-dark">{m.desc}</p>
            </div>
          ))}
        </div>

        <h2 className="mt-10 font-display text-xl font-semibold text-text-light dark:text-text-dark">Project status</h2>
        <p className="mt-3 text-textmuted-light dark:text-textmuted-dark">
          All six AI models above are trained and functional. This frontend is the platform layer that will connect to
          them via the documented API contract, turning individual model outputs into one coherent classroom experience
          for teachers and students.
        </p>
      </div>
    </div>
  )
}
