import { AppShell } from "@/components/layout/AppShell";
import { TeacherClassesCard } from "@/components/dashboard/TeacherClassesCard";

// Dedicated classes-only destination for the teacher sidebar's
// "Classes" link (/teacher/classes). Shows ONLY "Your classes" -- no
// dashboard stats, alerts, or analytics widgets. Reuses the exact same
// TeacherClassesCard (and therefore the exact same classesApi.list
// fetch) as the Teacher Dashboard's own "Your classes" section, so
// there is only one class-list implementation to keep in sync.
export function TeacherClassesPage() {
  return (
    <AppShell role="teacher" title="Classes">
      <div className="space-y-6">
        <TeacherClassesCard />
      </div>
    </AppShell>
  );
}
