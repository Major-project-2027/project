import {
  CalendarCheck2,
  ClipboardList,
  ListChecks,
  Camera,
  Mic,
  Bell,
  Activity,
  Smile,
  Eye,
  User,
  Users,
  Smartphone,
  Plus,
} from "lucide-react";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { StatCard } from "@/components/dashboard/StatCard";
import { ClassCard } from "@/components/dashboard/ClassCard";
import { JoinClassModal } from "@/components/dashboard/JoinClassModal";
import { Button } from "@/components/ui/Button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { Switch } from "@/components/ui/Switch";
import { Badge } from "@/components/ui/Badge";

import {
  classesApi,
  notificationsApi,
  testsApi,
  monitoringApi,
} from "@/services/api/endpoints";

import { currentStudent } from "@/mocks/data";
import { relativeTime, formatDateTime } from "@/lib/utils";

export function StudentDashboardPage() {
  const [joinOpen, setJoinOpen] = useState(false);

  // ------------------------------------------------------------
  // EXISTING API DATA
  // ------------------------------------------------------------

  const classesQuery = useQuery({
  queryKey: ["classes"],
  queryFn: classesApi.list,
  refetchOnMount: "always",
});
  console.log("STUDENT CLASSES:", classesQuery.data);
  console.log("STUDENT CLASSES ERROR:", classesQuery.error);

  const notificationsQuery = useQuery({
    queryKey: ["notifications"],
    queryFn: notificationsApi.list,
  });

  const testsQuery = useQuery({
    queryKey: ["tests"],
    queryFn: testsApi.list,
  });

  // ------------------------------------------------------------
  // DEVICE STATE
  // ------------------------------------------------------------

  const [cameraOn, setCameraOn] = useState(
    currentStudent.cameraEnabled
  );

  const [micOn, setMicOn] = useState(
    currentStudent.micEnabled
  );

  // ------------------------------------------------------------
  // REAL AI MONITORING DATA
  // ------------------------------------------------------------

  const monitoringQuery = useQuery({
    queryKey: ["live-monitor"],
    queryFn: monitoringApi.liveStudents,
    refetchInterval: 1000,
  });

  /*
   * Backend response:
   *
   * {
   *   success: true,
   *   data: [
   *     {
   *       studentName,
   *       currentEmotion,
   *       currentEngagement,
   *       blinkCount,
   *       headPose,
   *       gaze,
   *       phoneDetected,
   *       personCount
   *     }
   *   ]
   * }
   *
   * Some API implementations may return the data array directly,
   * so handle both cases.
   */

  const monitoring = Array.isArray(monitoringQuery.data)
  ? monitoringQuery.data[0]
  : null

  const monitoringStudent = monitoring

  // ------------------------------------------------------------
  // REAL AI VALUES
  // ------------------------------------------------------------

  const engagement =
    monitoringStudent?.currentEngagement ??
    monitoringStudent?.engagement_score ??
    monitoringStudent?.engagement ??
    null;

  const emotion =
    monitoringStudent?.currentEmotion ??
    monitoringStudent?.emotion ??
    null;

  const blinkCount =
    monitoringStudent?.blinkCount ??
    monitoringStudent?.blink_count ??
    null;

  const headPose =
    monitoringStudent?.headPose ??
    monitoringStudent?.head_pose ??
    null;

  const gaze =
    monitoringStudent?.gaze ??
    null;

  const personCount =
    monitoringStudent?.personCount ??
    monitoringStudent?.person_count ??
    null;

  const phoneDetected =
    monitoringStudent?.phoneDetected ??
    monitoringStudent?.phone_detected ??
    null;

  // ------------------------------------------------------------
  // CLASSES
  // ------------------------------------------------------------

  const upcoming = (classesQuery.data ?? []).filter(
    (c) => c.status !== "completed"
  );

  const today = upcoming.slice(0, 4);

  const completed = (classesQuery.data ?? []).filter(
    (c) => c.status === "completed"
  );

  // ------------------------------------------------------------
  // TESTS
  // ------------------------------------------------------------

  const pendingTests = (testsQuery.data ?? []).filter(
    (t) => t.status === "scheduled"
  );

  // ------------------------------------------------------------
  // NOTIFICATIONS
  // ------------------------------------------------------------

  const unreadNotifications = (
    notificationsQuery.data ?? []
  ).filter((n) => !n.read);

  // ------------------------------------------------------------
  // DISPLAY HELPERS
  // ------------------------------------------------------------

  const displayValue = (
    value: unknown,
    fallback = "—"
  ) => {
    if (
      value === null ||
      value === undefined ||
      value === ""
    ) {
      return fallback;
    }

    return String(value);
  };

  return (
    <AppShell role="student" title="Student Dashboard">
      <div className="space-y-6">

        {/* ====================================================== */}
        {/* AI MONITORING STATS                                   */}
        {/* ====================================================== */}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">

          <StatCard
  label="Engagement"
  value={`${monitoring?.currentEngagement ?? monitoring?.engagement_score ?? 0}%`}
  icon={Activity}
  tone="engaged"
/>

<StatCard
  label="Emotion"
  value={monitoring?.currentEmotion ?? "Loading..."}
  icon={Smile}
  tone="focus"
/>

<StatCard
  label="Blink Count"
  value={String(monitoring?.blinkCount ?? 0)}
  icon={Eye}
  tone="attention"
/>

<StatCard
  label="Head Pose"
  value={monitoring?.headPose ?? "Loading..."}
  icon={User}
  tone="critical"
/>

<StatCard
  label="Persons"
  value={String(monitoring?.personCount ?? 0)}
  icon={Users}
  tone="focus"
/>

<StatCard
  label="Phone"
  value={monitoring?.phoneDetected ? "Detected" : "Not Detected"}
  icon={Smartphone}
  tone={monitoring?.phoneDetected ? "critical" : "engaged"}
/>

<StatCard
  label="Gaze"
  value={monitoring?.gaze ?? "Loading..."}
  icon={Eye}
  tone="attention"
/>

        </div>

        {/* ====================================================== */}
        {/* CLASS / TEST AREA                                     */}
        {/* ====================================================== */}

        <div className="grid gap-6 lg:grid-cols-3">

          <div className="lg:col-span-2 space-y-6">

            {/* -------------------------------------------------- */}
            {/* UPCOMING CLASSES                                  */}
            {/* -------------------------------------------------- */}

            <Card>
              <CardHeader className="flex-col items-stretch gap-3 pb-3 sm:flex-row sm:items-center">
                <div>
                  <CardTitle>
                    Upcoming classes
                  </CardTitle>

                  <CardDescription>
                    Join a live session or view what's scheduled
                  </CardDescription>
                </div>

                <div className="sm:ml-auto">
                  <Button size="sm" onClick={() => setJoinOpen(true)}>
                    <Plus className="h-4 w-4" />
                    Join class
                  </Button>
                </div>
              </CardHeader>

              <CardContent className="pt-3">

                {classesQuery.isLoading ? (
                  <div className="grid gap-4 sm:grid-cols-2">
                    {Array.from({ length: 4 }).map(
                      (_, i) => (
                        <Skeleton
                          key={i}
                          className="h-40"
                        />
                      )
                    )}
                  </div>
                ) : today.length === 0 ? (
                  <EmptyState
                    icon={CalendarCheck2}
                    title="Nothing scheduled"
                    description="Your upcoming classes will show up here."
                  />
                ) : (
                  <div className="grid gap-4 sm:grid-cols-2">
                    {today.map((c) => (
                      <ClassCard
                        key={c.id}
                        session={c}
                        role="student"
                      />
                    ))}
                  </div>
                )}

              </CardContent>
            </Card>

            {/* -------------------------------------------------- */}
            {/* COMPLETED CLASSES                                 */}
            {/* -------------------------------------------------- */}

            {completed.length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle>Completed classes</CardTitle>
                  <CardDescription>
                    Open a class to see your monitoring summary
                  </CardDescription>
                </CardHeader>

                <CardContent className="pt-3">
                  <div className="grid gap-4 sm:grid-cols-2">
                    {completed.map((c) => (
                      <ClassCard
                        key={c.id}
                        session={c}
                        role="student"
                      />
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* -------------------------------------------------- */}
            {/* TESTS                                              */}
            {/* -------------------------------------------------- */}

            <Card>
              <CardHeader className="pb-3">
                <CardTitle>
                  Tests & assignments
                </CardTitle>

                <CardDescription>
                  Stay on top of what's due
                </CardDescription>
              </CardHeader>

              <CardContent className="pt-3 space-y-2">

                {(testsQuery.data ?? []).length === 0 ? (
                  <EmptyState
                    icon={ListChecks}
                    title="No tests available"
                    description="Your scheduled tests will appear here."
                  />
                ) : (
                  (testsQuery.data ?? []).map((t) => (
                    <div
                      key={t.id}
                      className="flex items-center justify-between rounded-lg border border-border-light p-3 dark:border-border-dark"
                    >
                      <div>
                        <p className="text-sm font-medium text-text-light dark:text-text-dark">
                          {t.title}
                        </p>

                        <p className="text-xs text-textmuted-light dark:text-textmuted-dark">
                          {t.subject} · {t.durationMinutes} min ·{" "}
                          {formatDateTime(t.scheduledStart)}
                        </p>
                      </div>

                      <Badge
                        variant={
                          t.status === "scheduled"
                            ? "attention"
                            : t.status === "completed"
                              ? "engaged"
                              : "neutral"
                        }
                      >
                        {t.status}
                      </Badge>
                    </div>
                  ))
                )}

              </CardContent>
            </Card>

          </div>

          {/* ==================================================== */}
          {/* RIGHT SIDE                                           */}
          {/* ==================================================== */}

          <div className="space-y-6">

            {/* -------------------------------------------------- */}
            {/* DEVICE STATUS                                      */}
            {/* -------------------------------------------------- */}

            <Card>
              <CardHeader className="pb-3">
                <CardTitle>
                  Device status
                </CardTitle>

                <CardDescription>
                  Controls used during live sessions
                </CardDescription>
              </CardHeader>

              <CardContent className="space-y-4 pt-3">

                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-sm text-text-light dark:text-text-dark">
                    <Camera className="h-4 w-4" />
                    Camera
                  </span>

                  <Switch
                    checked={cameraOn}
                    onChange={setCameraOn}
                    label="Toggle camera"
                  />
                </div>

                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-sm text-text-light dark:text-text-dark">
                    <Mic className="h-4 w-4" />
                    Microphone
                  </span>

                  <Switch
                    checked={micOn}
                    onChange={setMicOn}
                    label="Toggle microphone"
                  />
                </div>

                <p className="rounded-lg bg-focus-500/5 p-2.5 text-xs text-textmuted-light dark:text-textmuted-dark">
                  Face authentication is required before joining
                  any monitored session. Your teacher controls
                  whether camera use is mandatory for a given class.
                </p>

              </CardContent>
            </Card>

            {/* -------------------------------------------------- */}
            {/* NOTIFICATIONS                                      */}
            {/* -------------------------------------------------- */}

            <Card>
              <CardHeader className="pb-3">
                <CardTitle>
                  Notifications
                </CardTitle>
              </CardHeader>

              <CardContent className="pt-3">

                {notificationsQuery.isLoading ? (
                  <div className="space-y-3">
                    {Array.from({ length: 3 }).map(
                      (_, i) => (
                        <Skeleton
                          key={i}
                          className="h-12"
                        />
                      )
                    )}
                  </div>
                ) : unreadNotifications.length === 0 ? (
                  <EmptyState
                    icon={Bell}
                    title="No notifications"
                    description="You have no unread notifications."
                  />
                ) : (
                  <ul className="space-y-1">
                    {unreadNotifications
                      .slice(0, 5)
                      .map((n) => (
                        <li
                          key={n.id}
                          className="rounded-lg px-2 py-2 hover:bg-black/5 dark:hover:bg-white/5"
                        >
                          <p className="text-sm font-medium text-text-light dark:text-text-dark">
                            {n.title}
                          </p>

                          <p className="text-xs text-textmuted-light dark:text-textmuted-dark">
                            {relativeTime(n.timestamp)}
                          </p>
                        </li>
                      ))}
                  </ul>
                )}

              </CardContent>
            </Card>

          </div>
        </div>
      </div>
      <JoinClassModal open={joinOpen} onClose={() => setJoinOpen(false)} />
    </AppShell>
  );
}