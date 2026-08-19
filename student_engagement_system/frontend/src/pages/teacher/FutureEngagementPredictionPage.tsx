import { useQuery } from "@tanstack/react-query";
import { Sparkles, AlertCircle } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Badge } from "@/components/ui/Badge";
import { Avatar } from "@/components/ui/Avatar";

import { futureEngagementApi } from "@/services/api/endpoints";
import {
  relativeTime,
  futureEngagementLabelText,
  futureEngagementLabelTone,
} from "@/lib/utils";

// Separate destination from the live "AI Monitoring" panel (see
// ParticipantsPanel.tsx) -- this list is built entirely from students'
// COMPLETED sessions, ranked lowest predicted future engagement first,
// per the spec.
export function FutureEngagementPredictionPage() {
  const query = useQuery({
    queryKey: ["future-engagement-predictions", "teacher"],
    queryFn: futureEngagementApi.teacherList,
    refetchOnMount: "always",
    refetchInterval: 60000,
  });

  const ready = query.data?.ready ?? [];
  const insufficient = query.data?.insufficient ?? [];

  return (
    <AppShell role="teacher" title="Future Engagement Prediction">
      <div className="space-y-6">
        <Card>
          <CardHeader className="pb-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-focus-500" />
                Future engagement prediction
              </CardTitle>
              <CardDescription>
                Every student in your classes, ranked from lowest to highest predicted engagement in their next class — based on each student's own completed-session history
              </CardDescription>
            </div>
          </CardHeader>

          <CardContent className="pt-3">
            {query.isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-14" />
                ))}
              </div>
            ) : query.isError ? (
              <ErrorState onRetry={() => query.refetch()} />
            ) : ready.length === 0 && insufficient.length === 0 ? (
              <EmptyState
                icon={Sparkles}
                title="No students yet"
                description="Once students join your classes, their future engagement predictions will appear here."
              />
            ) : ready.length === 0 ? (
              <EmptyState
                icon={AlertCircle}
                title="Not enough historical data yet"
                description="No student in your classes has completed at least 3 sessions with usable engagement data yet."
              />
            ) : (
              <ul className="divide-y divide-border-light dark:divide-border-dark">
                {ready.map((row, index) => (
                  <li
                    key={row.studentId}
                    className="flex items-center gap-3 py-3"
                  >
                    <span className="w-6 shrink-0 text-right text-xs text-textmuted-light dark:text-textmuted-dark">
                      {index + 1}.
                    </span>
                    <Avatar name={row.studentName} size={36} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-text-light dark:text-text-dark">
                        {row.studentName}
                      </p>
                      <p className="truncate text-xs text-textmuted-light dark:text-textmuted-dark">
                        {row.usn ? `${row.usn} · ` : ""}
                        {row.historicalSessionsUsed} historical sessions analyzed
                        {row.generatedAt && ` · updated ${relativeTime(row.generatedAt)}`}
                      </p>
                    </div>
                    <Badge variant={futureEngagementLabelTone(row.statusLabel)}>
                      {futureEngagementLabelText(row.statusLabel)}
                    </Badge>
                    <span className="w-14 shrink-0 text-right text-lg font-semibold text-text-light dark:text-text-dark">
                      {Math.round(row.predictionScore ?? 0)}%
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {insufficient.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Insufficient data</CardTitle>
              <CardDescription>
                These students haven't completed at least 3 sessions with usable engagement data yet, so no prediction is generated for them — they are never shown as 0%.
              </CardDescription>
            </CardHeader>

            <CardContent className="pt-3">
              <ul className="divide-y divide-border-light dark:divide-border-dark">
                {insufficient.map((row) => (
                  <li
                    key={row.studentId}
                    className="flex items-center gap-3 py-3"
                  >
                    <Avatar name={row.studentName} size={32} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-text-light dark:text-text-dark">
                        {row.studentName}
                      </p>
                      <p className="truncate text-xs text-textmuted-light dark:text-textmuted-dark">
                        {row.usn ? `${row.usn} · ` : ""}
                        {row.status === "insufficient_data"
                          ? `${row.historicalSessionsUsed}/3 completed sessions so far`
                          : "Prediction unavailable"}
                      </p>
                    </div>
                    <Badge variant="neutral">
                      {row.status === "insufficient_data" ? "Not enough data" : "Unavailable"}
                    </Badge>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
