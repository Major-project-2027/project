import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Radio, LogIn } from "lucide-react";

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
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";

import { classesApi } from "@/services/api/endpoints";
import { formatTime } from "@/lib/utils";

// Any class with an active session right now, across every teacher --
// no class code required to join. Shared by the Student Dashboard and
// the dedicated Student Classes page (/student/classes) so both render
// from exactly one live-class fetch/UI implementation, never two
// diverging copies.
export function LiveClassesCard() {
  const navigate = useNavigate();

  const liveClassesQuery = useQuery({
    queryKey: ["live-classes"],
    queryFn: classesApi.liveClasses,
    refetchInterval: 10000,
  });

  // Joining a live class requires face verification first (Feature 2) --
  // this hands off to /student/verify/:classId, which performs the real
  // camera-based check and only then calls classesApi.joinLive itself,
  // once the backend has confirmed the match.
  const goToFaceVerification = (classId: string) => {
    navigate(`/student/verify/${classId}`);
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div>
          <CardTitle className="flex items-center gap-2">
            <span className="flex h-2 w-2 animate-pulse rounded-full bg-critical-500" />
            Live classes
          </CardTitle>
          <CardDescription>
            Any class a teacher has started right now — join with one click, no code needed
          </CardDescription>
        </div>
      </CardHeader>

      <CardContent className="pt-3">
        {liveClassesQuery.isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        ) : (liveClassesQuery.data ?? []).length === 0 ? (
          <EmptyState
            icon={Radio}
            title="No live classes right now"
            description="When a teacher starts a class, it will appear here."
          />
        ) : (
          <ul className="space-y-2">
            {(liveClassesQuery.data ?? []).map((c) => (
              <li
                key={c.sessionId}
                className="flex items-center justify-between gap-3 rounded-xl border border-border-light p-3 dark:border-border-dark"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <Avatar name={c.teacherName || c.title} size={36} />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="truncate text-sm font-medium text-text-light dark:text-text-dark">
                        {c.title}
                      </p>
                      <Badge variant="critical">
                        <Radio className="h-3 w-3" />
                        Live
                      </Badge>
                    </div>
                    <p className="truncate text-xs text-textmuted-light dark:text-textmuted-dark">
                      {c.subject} · {c.teacherName} · started {formatTime(c.startTime)}
                      {c.studentCount > 0 && ` · ${c.studentCount} joined`}
                    </p>
                  </div>
                </div>

                <Button
                  size="sm"
                  onClick={() => goToFaceVerification(c.classId)}
                >
                  <LogIn className="h-4 w-4" />
                  Join class
                </Button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
