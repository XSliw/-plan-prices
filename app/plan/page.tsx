"use client"

import { useEffect, useMemo, useState, type CSSProperties } from "react"
import { Activity, CalendarDays, Check, ChevronDown, CircleHelp, Crosshair, Gauge, LayoutDashboard, Search, Target, TrendingUp } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { glossary, trainingDays, type TrainingDay, weekKm } from "@/lib/training-plan"

type Tab = "overview" | "today" | "weeks" | "months" | "goals"
const tabs: { id: Tab; label: string; icon: typeof Target }[] = [
  { id: "overview", label: "Обзор", icon: LayoutDashboard }, { id: "today", label: "Сегодня", icon: Gauge },
  { id: "weeks", label: "Недели", icon: CalendarDays }, { id: "months", label: "Месяцы", icon: Crosshair },
  { id: "goals", label: "Цели", icon: Target },
]
const categoryLabel: Record<TrainingDay["category"], string> = { бег: "Бег", силовая: "Силовая", техника: "Техника", восстановление: "Восстановление" }

const dateText = (date: Date) => new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" }).format(date)
const fullDate = (date: Date) => new Intl.DateTimeFormat("ru-RU", { weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(date)

function DayCard({ day, done, onToggle, defaultOpen = false }: { day: TrainingDay; done: boolean; onToggle: () => void; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <article className={cn("overflow-hidden rounded-2xl border bg-card", done && "border-primary/50")}>
      <button className="flex w-full items-start gap-3 p-4 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className={cn("mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-xl bg-secondary text-sm font-bold", done && "bg-primary text-primary-foreground")}>{done ? <Check aria-hidden="true" /> : day.date.getDate()}</span>
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="flex flex-wrap items-center gap-2"><strong className="text-pretty">{day.dayName}: {day.title}</strong><span className={`tag tag-${day.category}`}>{categoryLabel[day.category]}</span></span>
          <span className="text-sm text-muted-foreground">{dateText(day.date)} · {day.duration}</span>
        </span>
        <ChevronDown aria-hidden="true" className={cn("mt-2 shrink-0 transition-transform", open && "rotate-180")} />
      </button>
      {open && <div className="flex flex-col gap-5 border-t p-4">
        <section className="summary-grid">
          <div><span>Цель</span><p>{day.goal}</p></div><div><span>Интенсивность</span><p>{day.intensity}</p></div>
          <div><span>Оборудование</span><p>{day.equipment}</p></div><div><span>Порядок</span><p>{day.order}</p></div>
        </section>
        <div className="flex flex-col gap-3">
          {day.blocks.map((trainingBlock, blockIndex) => <section className="block-card" key={`${day.id}-${blockIndex}`}>
            <header><span>{String(blockIndex + 1).padStart(2, "0")}</span><div><h3>{trainingBlock.title}</h3><p>{trainingBlock.time}</p></div></header>
            <ol>{trainingBlock.steps.map((step, index) => <li key={index}><span>{index + 1}</span><p>{step}</p></li>)}</ol>
            <p className="transition-note"><strong>Переход:</strong> {trainingBlock.restAfter}</p>
          </section>)}
        </div>
        <aside className="finish-note"><strong>Когда остановиться</strong><p>{day.finish}</p></aside>
        <Button onClick={onToggle} variant={done ? "outline" : "default"} size="lg" className="min-h-11 w-full">{done ? "Снять отметку" : "Отметить тренировку выполненной"}</Button>
      </div>}
    </article>
  )
}

function currentDayIndex() {
  const today = new Date()
  const found = trainingDays.findIndex(day => day.date.toDateString() === today.toDateString())
  return found >= 0 ? found : today < trainingDays[0].date ? 0 : trainingDays.length - 1
}

function OverviewView({ done, goToday, goWeek }: { done: Set<string>; goToday: () => void; goWeek: (week: number) => void }) {
  const index = currentDayIndex()
  const current = trainingDays[index]
  const eligible = trainingDays.slice(0, index + 1)
  const completed = trainingDays.filter(day => done.has(day.id)).length
  const missed = eligible.filter(day => !done.has(day.id)).length
  const percent = Math.round(completed / trainingDays.length * 100)
  const weekCounts = Array.from({ length: 33 }, (_, i) => trainingDays.filter(day => day.week === i + 1 && done.has(day.id)).length)
  let streak = 0
  for (let week = current.week - 1; week >= 1; week--) { if (weekCounts[week - 1] === 7) streak += 1; else break }
  const monthKeys = Array.from(new Set(trainingDays.map(day => `${day.date.getFullYear()}-${day.date.getMonth()}`)))
  const monthData = monthKeys.map(key => { const [year, month] = key.split("-").map(Number); return { label: new Intl.DateTimeFormat("ru-RU", { month: "short" }).format(new Date(year, month, 1)).replace(".", ""), value: trainingDays.filter(day => `${day.date.getFullYear()}-${day.date.getMonth()}` === key && done.has(day.id)).length } })
  const maxMonth = Math.max(1, ...monthData.map(item => item.value))
  const phase = current.week <= 7 ? "Подготовка и восстановление" : current.week <= 15 ? "Возврат к бегу" : current.week <= 27 ? "Основной блок" : current.week <= 31 ? "Специальная подготовка" : "Подводка"
  return <div className="flex flex-col gap-5">
    <header className="overview-hero"><div><p className="eyebrow">План подготовки 4.2</p><h1>Твой прогресс</h1><p>Неделя {current.week} из 33 · {phase}</p></div><div className="progress-ring" style={{ "--progress": `${percent * 3.6}deg` } as CSSProperties}><strong>{percent}%</strong><span>выполнено</span></div></header>
    <Button size="lg" className="min-h-14 w-full justify-between" onClick={goToday}><span>Открыть тренировку на сегодня</span><ChevronDown className="-rotate-90" aria-hidden="true" /></Button>
    <section className="metric-grid" aria-label="Показатели прогресса">
      <article><Activity aria-hidden="true"/><strong>{streak}</strong><span>полных недель подряд</span></article>
      <article><Check aria-hidden="true"/><strong>{completed}<small> / {trainingDays.length}</small></strong><span>дней выполнено</span></article>
      <article><CalendarDays aria-hidden="true"/><strong>{missed}</strong><span>прошедших не отмечено</span></article>
      <article><TrendingUp aria-hidden="true"/><strong>{weekCounts[current.week - 1]}<small> / 7</small></strong><span>текущая неделя</span></article>
    </section>
    <section className="dashboard-card"><div className="dashboard-heading"><div><p className="eyebrow">Календарь цикла</p><h2>33 недели</h2></div><span>{completed} отметок</span></div><div className="week-matrix">{weekCounts.map((count, i) => { const week = i + 1; return <button key={week} onClick={() => goWeek(week)} className={cn(count === 7 && "complete", week === current.week && "current", week < current.week && count < 7 && "missed")} aria-label={`Неделя ${week}: ${count} из 7 выполнено`}><strong>{week}</strong><span>{count}/7</span></button> })}</div></section>
    <section className="dashboard-card"><div className="dashboard-heading"><div><p className="eyebrow">Ритм работы</p><h2>Активность по месяцам</h2></div></div><div className="month-chart">{monthData.map(item => <div key={item.label}><div className="bar-track"><span style={{ height: `${Math.max(4, item.value / maxMonth * 100)}%` }} /></div><strong>{item.value}</strong><small>{item.label}</small></div>)}</div></section>
  </div>
}

function TodayView({ done, toggle }: { done: Set<string>; toggle: (id: string) => void }) {
  const today = new Date()
  let index = trainingDays.findIndex(day => day.date.toDateString() === today.toDateString())
  if (index < 0) index = today < trainingDays[0].date ? 0 : trainingDays.length - 1
  const current = trainingDays[index]
  const tomorrow = trainingDays[Math.min(index + 1, trainingDays.length - 1)]
  const weekDone = trainingDays.filter(day => day.week === current.week && done.has(day.id)).length
  return <div className="flex flex-col gap-5">
    <section className="hero-panel"><div><p className="eyebrow">План 4.2 · Неделя {current.week}</p><h1 className="text-balance">Тренировка без догадок</h1><p>{fullDate(current.date)}</p></div><div className="week-score"><strong>{weekDone}/7</strong><span>дней недели</span></div></section>
    <section className="flex flex-col gap-3"><div className="section-heading"><div><p className="eyebrow">Основное</p><h2>Сегодня</h2></div><span>{weekKm[current.week - 1]} км / нед.</span></div><DayCard day={current} done={done.has(current.id)} onToggle={() => toggle(current.id)} defaultOpen /></section>
    {tomorrow.id !== current.id && <section className="flex flex-col gap-3"><div className="section-heading"><div><p className="eyebrow">Подготовься заранее</p><h2>Завтра</h2></div></div><DayCard day={tomorrow} done={done.has(tomorrow.id)} onToggle={() => toggle(tomorrow.id)} /></section>}
    <Glossary />
  </div>
}

function Glossary() { return <details className="rounded-2xl border bg-card p-4"><summary className="flex cursor-pointer items-center gap-2 font-semibold"><CircleHelp aria-hidden="true" /> Словарь новичка</summary><dl className="mt-4 grid gap-3">{glossary.map(([term, meaning]) => <div key={term}><dt>{term}</dt><dd>{meaning}</dd></div>)}</dl></details> }

function WeeksView({ done, toggle, selectedWeek }: { done: Set<string>; toggle: (id: string) => void; selectedWeek: number }) {
  const [query, setQuery] = useState("")
  const [filter, setFilter] = useState("все")
  const [openWeek, setOpenWeek] = useState(selectedWeek)
  return <div className="flex flex-col gap-5"><header><p className="eyebrow">Полный календарь</p><h1>33 недели · 231 день</h1><p className="mt-2 text-muted-foreground">Каждый день расписан полностью: от первой минуты разминки до заминки.</p></header>
    <label className="search-box"><Search aria-hidden="true" /><span className="sr-only">Поиск упражнения</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Найти: гиря, КСУ, 800 м…" /></label>
    <div className="filter-row">{["все", "бег", "силовая", "техника", "восстановление"].map(item => <button key={item} onClick={() => setFilter(item)} className={cn(filter === item && "active")}>{item === "все" ? "Все" : categoryLabel[item as TrainingDay["category"]]}</button>)}</div>
    <div className="flex flex-col gap-3">{Array.from({ length: 33 }, (_, i) => i + 1).map(week => {
      const days = trainingDays.filter(day => day.week === week).filter(day => filter === "все" || day.category === filter).filter(day => !query || JSON.stringify(day).toLowerCase().includes(query.toLowerCase()))
      if (!days.length) return null
      const count = trainingDays.filter(day => day.week === week && done.has(day.id)).length
      return <section className="week-card" key={week}><button onClick={() => setOpenWeek(openWeek === week ? 0 : week)}><div><span>Неделя {week}</span><strong>{weekKm[week - 1]} км · {count}/7 выполнено</strong></div><ChevronDown aria-hidden="true" className={cn(openWeek === week && "rotate-180")} /></button>{openWeek === week && <div className="flex flex-col gap-3 border-t p-3">{days.map(day => <DayCard key={day.id} day={day} done={done.has(day.id)} onToggle={() => toggle(day.id)} />)}</div>}</section>
    })}</div><Glossary /></div>
}

function MonthsView({ done }: { done: Set<string> }) {
  const months = Array.from(new Set(trainingDays.map(day => `${day.date.getFullYear()}-${day.date.getMonth()}`)))
  return <div className="flex flex-col gap-5"><header><p className="eyebrow">Контроль нагрузки</p><h1>Месяцы и этапы</h1></header><div className="grid gap-3 md:grid-cols-2">{months.map(key => { const [year, month] = key.split("-").map(Number); const days = trainingDays.filter(day => day.date.getFullYear() === year && day.date.getMonth() === month); const complete = days.filter(day => done.has(day.id)).length; return <article className="month-card" key={key}><p>{new Intl.DateTimeFormat("ru-RU", { month: "long", year: "numeric" }).format(new Date(year, month, 1))}</p><strong>{days[0].week}–{days.at(-1)?.week} недели</strong><div><span style={{ width: `${complete / days.length * 100}%` }} /></div><small>{complete} из {days.length} дней · бег до {Math.max(...days.map(day => weekKm[day.week - 1]))} км/нед.</small></article> })}</div></div>
}

function GoalsView() { const goals = ["5 км — около 17:00", "3 км — менее 10:00", "40 подтягиваний", "90 отжиманий на брусьях", "20 КСУ", "+16 кг: 17 подтягиваний и 25 брусьев", "Рывок 24 кг — 60 повторений", "Мяч 5 кг — сумма 38 м", "Челноки: 10×10 м за 25–26 с; 4×10 м за 9,0 с", "Спецкросс 2 км — около 10 минут"]
  return <div className="flex flex-col gap-5"><header><p className="eyebrow">Контроль 15 февраля 2027</p><h1>Все цели одновременно</h1><p className="mt-2 text-muted-foreground">План повышает вероятность результата, но не является медицинской или физиологической гарантией.</p></header><div className="goal-grid">{goals.map((goal, index) => <article key={goal}><span>{String(index + 1).padStart(2, "0")}</span><p>{goal}</p></article>)}</div><aside className="finish-note"><strong>Правило прогрессии</strong><p>Не догоняй пропущенную работу. Увеличивай нагрузку только после двух недель без боли, отёка, подкашивания и ухудшения на следующее утро. Бег и прыжки выполняются только после допуска профильного врача.</p></aside><Glossary /></div> }

export default function Page() {
  const [tab, setTab] = useState<Tab>("overview")
  const [selectedWeek, setSelectedWeek] = useState(1)
  const [done, setDone] = useState<Set<string>>(new Set())
  useEffect(() => { try { const stored = localStorage.getItem("training-plan-v4-progress"); if (stored) setDone(new Set(JSON.parse(stored))) } catch {} }, [])
  const toggle = (id: string) => setDone(previous => { const next = new Set(previous); next.has(id) ? next.delete(id) : next.add(id); localStorage.setItem("training-plan-v4-progress", JSON.stringify([...next])); return next })
  const openWeek = (week: number) => { setSelectedWeek(week); setTab("weeks") }
  const content = useMemo(() => tab === "overview" ? <OverviewView done={done} goToday={() => setTab("today")} goWeek={openWeek} /> : tab === "today" ? <TodayView done={done} toggle={toggle} /> : tab === "weeks" ? <WeeksView key={selectedWeek} done={done} toggle={toggle} selectedWeek={selectedWeek} /> : tab === "months" ? <MonthsView done={done} /> : <GoalsView />, [tab, done, selectedWeek])
  return <main className="min-h-screen bg-background pb-28 text-foreground"><div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-3 py-5 sm:px-5">{content}</div><nav className="bottom-nav" aria-label="Основная навигация">{tabs.map(item => { const Icon = item.icon; return <button key={item.id} onClick={() => setTab(item.id)} className={cn(tab === item.id && "active")} aria-current={tab === item.id ? "page" : undefined}><Icon aria-hidden="true" /><span>{item.label}</span></button> })}</nav></main>
}
