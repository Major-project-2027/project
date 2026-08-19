import {
  CalendarCheck2,
  Plus,
  Sparkles,
} from "lucide-react";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { ClassCard } from "@/components/dashboard/ClassCard";
import { LiveClassesCard } from "@/components/dashboard/LiveClassesCard";
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
import { Badge } from "@/components/ui/Badge";

import {
  classesApi,
  futureEngagementApi,
} from "@/services/api/endpoints";

import {
  formatDateTime,
  futureEngagementLabelText,
  futureEngagementLabelTone,
} from "@/lib/utils";

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

  // ------------------------------------------------------------
  // FUTURE ENGAGEMENT PREDICTION -- built from this student's own
  // COMPLETED sessions only (never a live/current session, never a
  // classmate's data -- the backend derives the student from the auth
  // token). Not gated on being in a live class at all. A modest refetch
  // interval is enough since the backend itself only actually
  // recomputes when new completed-session data exists.
  // ------------------------------------------------------------

  const futurePredictionQuery = useQuery({
    queryKey: ["future-engagement-prediction"],
    queryFn: futureEngagementApi.student,
    refetchOnMount: "always",
    refetchInterval: 60000,
  });

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

  return (
    <AppShell role="student" title="Student Dashboard">
      <div className="space-y-6">

            {/* -------------------------------------------------- */}
            {/* LIVE CLASSES                                      */}
            {/* -------------------------------------------------- */}

            <LiveClassesCard />

            {/* -------------------------------------------------- */}
            {/* FUTURE ENGAGEMENT PREDICTION -- historical/cross-  */}
            {/* session, based on completed session history        */}
            {/* -------------------------------------------------- */}

            <Card>
              <CardHeader className="pb-3">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-focus-500" />
                    Future engagement prediction
                  </CardTitle>
                  <CardDescription>
                    Predicted engagement for your next class, based on your completed session history
                  </CardDescription>
                </div>
              </CardHeader>

              <CardContent className="pt-3">
                {futurePredictionQuery.isLoading ? (
                  <Skeleton className="h-24" />
                ) : !futurePredictionQuery.data || futurePredictionQuery.data.status === "insufficient_data" ? (
                  <div>
                    <p className="text-sm font-medium text-text-light dark:text-text-dark">
                      Not enough historical data
                    </p>
                    <p className="mt-1 text-sm text-textmuted-light dark:text-textmuted-dark">
                      Complete at least 3 sessions to generate a future engagement prediction.
                    </p>
                    {futurePredictionQuery.data && (
                      <p className="mt-1 text-xs text-textmuted-light dark:text-textmuted-dark">
                        {futurePredictionQuery.data.historical_sessions_used}/3 completed sessions so far
                      </p>
                    )}
                  </div>
                ) : futurePredictionQuery.data.status !== "ready" || typeof futurePredictionQuery.data.prediction_score !== "number" ? (
                  <p className="text-sm text-textmuted-light dark:text-textmuted-dark">
                    Future engagement prediction is temporarily unavailable
                    {futurePredictionQuery.data.reason ? `: ${futurePredictionQuery.data.reason}` : "."}
                  </p>
                ) : (
                  <div className="space-y-3">
                    <div className="flex items-center gap-4">
                      <div>
                        <p className="text-xs text-textmuted-light dark:text-textmuted-dark">
                          Predicted future engagement
                        </p>
                        <p className="text-2xl font-semibold text-text-light dark:text-text-dark">
                          {Math.round(futurePredictionQuery.data.prediction_score)}%
                        </p>
                      </div>

                      <Badge variant={futureEngagementLabelTone(futurePredictionQuery.data.status_label)}>
                        {futureEngagementLabelText(futurePredictionQuery.data.status_label)}
                      </Badge>
                    </div>

                    <p className="text-xs text-textmuted-light dark:text-textmuted-dark">
                      Historical sessions analyzed: {futurePredictionQuery.data.historical_sessions_used}
                    </p>

                    {futurePredictionQuery.data.generated_at && (
                      <p className="text-xs text-textmuted-light dark:text-textmuted-dark">
                        Last updated: {formatDateTime(futurePredictionQuery.data.generated_at)}
                      </p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>

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

      </div>
      <JoinClassModal open={joinOpen} onClose={() => setJoinOpen(false)} />
    </AppShell>
  );
}