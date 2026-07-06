/**
 * AI Report Page — LLM-powered hydraulic engineering reports.
 */

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FileText, Languages, RefreshCw, Copy, CheckCircle, AlertTriangle } from 'lucide-react'
import { useReport } from '../hooks/useApi'
import { LeakReport, Language } from '../types'
import { getSeverityColor, formatPressure, formatFlow, formatPercent, cn } from '../utils'

interface ReportPageProps {
  leakReport: LeakReport | null
}

export function ReportPage({ leakReport }: ReportPageProps) {
  const [language, setLanguage] = useState<Language>('en')
  const [context, setContext] = useState('')
  const [copied, setCopied] = useState(false)
  const { fetchReport, report, loading, error } = useReport()

  const handleGenerate = () => {
    fetchReport(language, context || undefined)
  }

  const handleCopy = () => {
    if (report?.report) {
      navigator.clipboard.writeText(report.report)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full max-w-4xl mx-auto">

      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2.5 rounded-xl bg-cyan-500/15 border border-cyan-500/20">
          <FileText className="text-cyan-400" size={20} />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-white">AI Hydraulic Report</h1>
          <p className="text-xs text-white/40">AI-powered analysis for water utility operators</p>
        </div>
      </div>

      {/* Current leak summary */}
      {leakReport && (
        <div className={cn(
          'glass-card p-4 border',
          leakReport.detected ? 'border-red-500/30' : 'border-emerald-500/20'
        )}>
          <div className="flex items-start gap-3">
            {leakReport.detected
              ? <AlertTriangle className="text-red-400 mt-0.5 flex-shrink-0 animate-pulse" size={16} />
              : <CheckCircle className="text-emerald-400 mt-0.5 flex-shrink-0" size={16} />
            }
            <div className="flex-1">
              <p className={cn('text-sm font-semibold', leakReport.detected ? 'text-red-400' : 'text-emerald-400')}>
                {leakReport.detected ? 'Leak Detected — Report Ready' : 'System Normal — No Active Leaks'}
              </p>
              {leakReport.detected && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
                  {[
                    { label: 'Location', value: leakReport.location, alert: false },
                    { label: 'Probability', value: formatPercent(leakReport.probability), alert: leakReport.probability > 70 },
                    { label: 'Pressure Drop', value: formatPressure(leakReport.pressure_drop), alert: true },
                    { label: 'Flow Loss', value: formatFlow(leakReport.estimated_flow_loss), alert: true },
                  ].map(({ label, value, alert }) => (
                    <div key={label}>
                      <div className="text-[10px] text-white/30 uppercase tracking-wider mb-0.5">{label}</div>
                      <div className={cn('text-sm font-semibold font-mono', alert ? 'text-red-400' : 'text-white/80')}>
                        {value}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="glass-card p-4">
        <h2 className="text-sm font-semibold text-white mb-4">Report Configuration</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          {/* Language selector */}
          <div>
            <label className="block text-xs text-white/50 mb-2 flex items-center gap-1.5">
              <Languages size={12} /> Report Language
            </label>
            <div className="flex gap-2">
              {(['en', 'fr'] as Language[]).map((lang) => (
                <button
                  key={lang}
                  onClick={() => setLanguage(lang)}
                  className={cn(
                    'flex-1 py-2 rounded-lg text-sm font-medium border transition-all duration-200',
                    language === lang
                      ? 'bg-cyan-500/15 border-cyan-500/30 text-cyan-400'
                      : 'bg-white/[0.03] border-white/10 text-white/40 hover:text-white/70'
                  )}
                >
                  {lang === 'en' ? '🇬🇧 English' : '🇫🇷 Français'}
                </button>
              ))}
            </div>
          </div>

          {/* Operator context */}
          <div>
            <label className="block text-xs text-white/50 mb-2">
              Operator Notes (optional)
            </label>
            <input
              type="text"
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="e.g. Maintenance crew dispatched at 14:30"
              className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-white/80 placeholder-white/20 focus:outline-none focus:border-cyan-500/40 transition-colors"
            />
          </div>
        </div>

        <button
          onClick={handleGenerate}
          disabled={loading}
          className={cn(
            'w-full py-3 rounded-xl font-semibold text-sm transition-all duration-200 flex items-center justify-center gap-2',
            loading
              ? 'bg-white/5 text-white/30 cursor-not-allowed'
              : 'bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 text-white shadow-lg shadow-cyan-500/20'
          )}
        >
          {loading ? (
            <>
              <RefreshCw size={16} className="animate-spin" />
              Generating report...
            </>
          ) : (
            <>
              <FileText size={16} />
              Generate AI Report
            </>
          )}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="glass-card p-4 border border-red-500/30 bg-red-500/[0.05]">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {/* Report output */}
      <AnimatePresence>
        {report && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card overflow-hidden"
          >
            {/* Report header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06] bg-white/[0.02]">
              <div className="flex items-center gap-2">
                <FileText size={14} className="text-cyan-400" />
                <span className="text-sm font-medium text-white/80">
                  Maayan Leak Analysis Report
                </span>
                <span className="text-xs text-white/30 font-mono">
                  {new Date(report.generated_at).toLocaleString()}
                </span>
              </div>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-white/[0.05] hover:bg-white/[0.08] text-white/60 hover:text-white/80 transition-all border border-white/[0.08]"
              >
                {copied ? <CheckCircle size={12} className="text-emerald-400" /> : <Copy size={12} />}
                {copied ? 'Copied!' : 'Copy'}
              </button>
            </div>

            {/* Report body — render markdown-like content */}
            <div className="p-5">
              <div className="prose prose-sm max-w-none">
                {report.report.split('\n').map((line, i) => {
                  if (line.startsWith('## ')) return (
                    <h2 key={i} className="text-base font-bold text-white/90 mt-4 mb-2 first:mt-0">
                      {line.replace('## ', '')}
                    </h2>
                  )
                  if (line.startsWith('**') && line.endsWith('**')) return (
                    <p key={i} className="font-semibold text-white/80 text-sm mb-1">
                      {line.replace(/\*\*/g, '')}
                    </p>
                  )
                  if (line.startsWith('- ') || line.startsWith('* ')) return (
                    <div key={i} className="flex gap-2 text-sm text-white/60 mb-1 ml-3">
                      <span className="text-cyan-400 mt-0.5 flex-shrink-0">•</span>
                      <span>{line.slice(2)}</span>
                    </div>
                  )
                  if (line.match(/^\d+\. /)) return (
                    <div key={i} className="flex gap-2 text-sm text-white/60 mb-1 ml-3">
                      <span className="text-cyan-400 font-mono text-xs mt-0.5 flex-shrink-0 w-4">
                        {line.match(/^(\d+)\./)?.[1]}.
                      </span>
                      <span>{line.replace(/^\d+\. /, '')}</span>
                    </div>
                  )
                  if (line.trim() === '') return <div key={i} className="h-2" />
                  return (
                    <p key={i} className="text-sm text-white/60 mb-2 leading-relaxed">
                      {line.replace(/\*\*(.*?)\*\*/g, '$1')}
                    </p>
                  )
                })}
              </div>
            </div>

            {/* Footer */}
            <div className="px-5 py-3 border-t border-white/[0.06] bg-white/[0.01] flex items-center justify-between">
              <span className="text-xs text-white/20">
                Generated by {
                  report.provider === 'groq' ? 'Groq (Llama 3.3 70B)' :
                  report.provider === 'openai' ? 'OpenAI (GPT-4o-mini)' :
                  'Maayan template engine'
                } · Language: {report.language.toUpperCase()}
              </span>
              <span className="text-xs text-white/20">
                Powered by Maayan AI
              </span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
