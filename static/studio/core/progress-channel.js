import {readStamp,currentRead} from './async-state.js';

/** At most one read in flight; disposal aborts reads and all scheduled callbacks. */
export function watchProject(session, clock) {
  let timer,
    stopped = false;
  const clocks = setInterval(clock, 1000);
  const poll = async () => {
    let stamp;
    try {
      if (!session.working && !session.actionPending) {
        stamp=readStamp(session);
        const next = await session.request(
          `/projects/${session.project.id}`,
          "GET",
          undefined,
          session.controller.signal,
        );
        if (!stopped && currentRead(session,stamp,next)){session.awaitingStatus=false;session.connection?.(null);session.receive(next);}
      }
    } catch (e) {
      if (!stopped && e.name !== "AbortError" && (!stamp||session.project===stamp.project)) {
        session.connection?.(e);
        if (session.project.source_progress?.active)
          session.project.source_progress.transport_error =
            "连接中断，正在重试；以下为最后收到的进度";
        if (session.project.runtime)
          session.project.runtime.transport_error =
            "连接中断，正在重试；以下为最后收到的进度";
        session.emit("progress");
      }
    } finally {
      if (!stopped) timer = setTimeout(poll, 2000);
    }
  };
  timer = setTimeout(poll, 2000);
  return () => {
    stopped = true;
    clearTimeout(timer);
    clearInterval(clocks);
  };
}
