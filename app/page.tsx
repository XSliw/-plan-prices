import { Download, FileText } from "lucide-react"

export default function Page() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-6 text-foreground">
      <section className="flex w-full max-w-md flex-col items-center gap-6 rounded-2xl border border-border bg-card p-8 text-center shadow-sm">
        <span className="flex size-16 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <FileText aria-hidden="true" className="size-8" />
        </span>
        <div className="flex flex-col gap-2">
          <h1 className="text-balance text-2xl font-semibold">Итоговый план тренировок</h1>
          <p className="text-pretty leading-relaxed text-muted-foreground">
            Подробная программа подготовки на 2026–2027 год в формате PDF.
          </p>
        </div>
        <a
          className="flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-primary px-5 py-3 font-medium text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          href="/training-plan-2026-2027.pdf"
          download="training-plan-2026-2027.pdf"
        >
          <Download aria-hidden="true" className="size-5" />
          Скачать PDF
        </a>
        <a
          className="text-sm font-medium text-primary underline underline-offset-4"
          href="/training-plan-2026-2027.pdf"
          target="_blank"
          rel="noreferrer"
        >
          Открыть PDF в новой вкладке
        </a>
      </section>
    </main>
  )
}
