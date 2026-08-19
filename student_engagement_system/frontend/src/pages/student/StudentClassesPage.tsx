import { AppShell } from "@/components/layout/AppShell";
import { LiveClassesCard } from "@/components/dashboard/LiveClassesCard";

// Dedicated classes-only destination for the student sidebar's
// "Classes" link (/student/classes). Shows ONLY live-class
// discovery/join -- no Future Engagement Prediction, no upcoming/
// completed classes, no tests, no other dashboard content. Reuses the
// exact same LiveClassesCard (and therefore the exact same
// classesApi.liveClasses fetch) as the Student Dashboard's own Live
// Classes section, so there is only one live-class implementation to
// keep in sync, never two diverging copies.
export function StudentClassesPage() {
  return (
    <AppShell role="student" title="Classes">
      <div className="space-y-6">
        <LiveClassesCard />
      </div>
    </AppShell>
  );
}
