import React, { useState, useEffect, useRef } from 'react';
import {
  BookOpen,
  MessageSquare,
  BarChart2,
  Upload,
  Search,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  ExternalLink,
  FileText,
  Image as ImageIcon,
  Layers,
  ChevronRight,
  Database,
  Cpu,
  RefreshCw,
  X,
  FileCheck,
  Trash2,
  Loader2
} from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('chat'); // 'chat' | 'corpus' | 'benchmark'

  // Chat State
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Exam-Night Multimodal Study Companion initialized. All responses are strictly grounded in course slides, notes, and handwritten scans with exact page citations.',
      is_refusal: false,
      sources: []
    }
  ]);
  const [sessionId] = useState(() => `session_${Date.now()}`);

  // Page Inspector Drawer State
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [inspectingSource, setInspectingSource] = useState(null);
  const [zoomLevel, setZoomLevel] = useState(1.0);

  // Corpus State
  const [corpusDocs, setCorpusDocs] = useState([]);
  const [corpusLoading, setCorpusLoading] = useState(false);
  const [corpusStats, setCorpusStats] = useState({ total_documents: 0, total_pages: 0, total_chunks: 0 });
  const [corpusSearch, setCorpusSearch] = useState('');
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState(null);
  const [uploadTask, setUploadTask] = useState(null);


  // Benchmark State
  const [benchmarkLoading, setBenchmarkLoading] = useState(false);
  const [benchmarkData, setBenchmarkData] = useState(null);
  const [benchmarkFilter, setBenchmarkFilter] = useState('all'); // 'all' | 'target' | 'refusal' | 'failed'

  // System Health
  const [systemHealth, setSystemHealth] = useState({ healthy: false, qdrant: '', mongo: false });

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  useEffect(() => {
    fetchHealth();
    fetchCorpus();
  }, []);

  const fetchHealth = async () => {
    try {
      const res = await fetch('/api/health');
      if (res.ok) {
        const data = await res.json();
        setSystemHealth({
          healthy: true,
          qdrant: data.qdrant_collection,
          mongo: data.mongodb_connected
        });
      }
    } catch (e) {
      setSystemHealth({ healthy: false, qdrant: '', mongo: false });
    }
  };

  const fetchCorpus = async () => {
    setCorpusLoading(true);
    try {
      const res = await fetch('/api/corpus/documents');
      if (res.ok) {
        const data = await res.json();
        setCorpusDocs(data.documents || []);
        setCorpusStats({
          total_documents: data.total_documents || 0,
          total_pages: data.total_pages || 0,
          total_chunks: data.total_chunks || 0
        });
      }
    } catch (e) {
      console.error('Failed to load corpus', e);
    } finally {
      setCorpusLoading(false);
    }
  };

  const handleSendQuery = async (e) => {
    e?.preventDefault();
    if (!query.trim() || loading) return;

    const userText = query.trim();
    setQuery('');
    const newMessages = [...messages, { role: 'user', content: userText, sources: [] }];
    setMessages(newMessages);
    setLoading(true);

    try {
      const res = await fetch('/api/chat/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userText, session_id: sessionId })
      });

      if (!res.ok) {
        throw new Error(`Server returned HTTP ${res.status}`);
      }

      const data = await res.json();
      setMessages([
        ...newMessages,
        {
          role: 'assistant',
          content: data.answer,
          is_refusal: data.is_refusal,
          sources: data.sources || []
        }
      ]);
    } catch (err) {
      setMessages([
        ...newMessages,
        {
          role: 'assistant',
          content: 'An error occurred during retrieval. Ensure backend and vector services are active.',
          is_refusal: true,
          sources: []
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const openSourceInspector = (source) => {
    setInspectingSource(source);
    setZoomLevel(1.0);
    setInspectorOpen(true);
  };

  const handleFileUpload = async (e) => {
    e.preventDefault();
    if (!uploadFile || uploading) return;

    setUploading(true);
    setUploadMsg(null);
    setUploadTask({
      doc_id: null,
      filename: uploadFile.name,
      progress: 10,
      status_message: 'Uploading document to server...',
      status: 'processing'
    });

    const formData = new FormData();
    formData.append('file', uploadFile);

    try {
      const res = await fetch('/api/corpus/upload', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (res.status === 202 || res.ok) {
        const docId = data.doc_id;
        setUploadTask((prev) => ({
          ...prev,
          doc_id: docId,
          progress: 15,
          status_message: 'File received. Ingestion running in background...'
        }));

        // Poll status every 1.5 seconds
        const pollInterval = setInterval(async () => {
          try {
            const statusRes = await fetch(`/api/corpus/status/${docId}`);
            if (statusRes.ok) {
              const statusData = await statusRes.json();
              setUploadTask({
                doc_id: docId,
                filename: statusData.filename || uploadFile.name,
                progress: statusData.progress,
                status_message: statusData.status_message,
                status: statusData.status,
                error_message: statusData.error_message
              });

              if (statusData.status === 'ready') {
                clearInterval(pollInterval);
                setUploading(false);
                setUploadMsg({
                  type: 'success',
                  text: `Document '${statusData.filename || uploadFile.name}' processed and indexed successfully.`
                });
                fetchCorpus();
                setTimeout(() => {
                  setUploadModalOpen(false);
                  setUploadTask(null);
                  setUploadFile(null);
                  setUploadMsg(null);
                }, 2000);
              } else if (statusData.status === 'failed') {
                clearInterval(pollInterval);
                setUploading(false);
                setUploadMsg({
                  type: 'error',
                  text: statusData.error_message || 'Ingestion encountered an error.'
                });
              }
            }
          } catch (pollErr) {
            console.error('Polling error', pollErr);
          }
        }, 1500);
      } else {
        setUploading(false);
        setUploadTask(null);
        setUploadMsg({ type: 'error', text: data.detail || 'Upload failed' });
      }
    } catch (err) {
      setUploading(false);
      setUploadTask(null);
      setUploadMsg({ type: 'error', text: 'Network error during upload' });
    }
  };

  const handleDeleteDocument = async (docId, filename) => {
    if (!window.confirm(`Are you sure you want to remove "${filename}" from the corpus?`)) return;
    try {
      const res = await fetch(`/api/corpus/documents/${docId}`, { method: 'DELETE' });
      if (res.ok) {
        fetchCorpus();
      } else {
        const data = await res.json();
        alert(data.detail || 'Failed to delete document');
      }
    } catch (e) {
      console.error('Delete error', e);
      alert('Network error while deleting document');
    }
  };


  const handleRunBenchmark = async () => {
    setBenchmarkLoading(true);
    try {
      const res = await fetch('/api/benchmark/run', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setBenchmarkData(data);
      }
    } catch (err) {
      console.error('Benchmark run error', err);
    } finally {
      setBenchmarkLoading(false);
    }
  };

  const filteredBenchmarkQuestions = benchmarkData?.results.filter((q) => {
    if (benchmarkFilter === 'target') return !q.must_refuse;
    if (benchmarkFilter === 'refusal') return q.must_refuse;
    if (benchmarkFilter === 'failed') return !q.passed;
    return true;
  });

  const filteredDocs = corpusDocs.filter((d) =>
    d.filename.toLowerCase().includes(corpusSearch.toLowerCase())
  );

  return (
    <div className="flex h-screen w-screen flex-col bg-[#181414] text-[#FCF2E5] font-sans antialiased overflow-hidden select-none">
      {/* Top Header */}
      <header className="flex h-14 items-center justify-between border-b border-[#524646]/70 bg-[#231d1d] px-6">
        <div className="flex items-center space-x-2.5">
          <div className="relative flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-tr from-[#EC5B38] via-[#e5502c] to-[#f98a6f] shadow-md shadow-[#EC5B38]/30">
            <span className="text-xs font-black tracking-widest text-[#FCF2E5]">VS</span>
            <div className="absolute -inset-0.5 rounded-xl bg-gradient-to-tr from-[#EC5B38] to-[#FCF2E5] opacity-25 blur-[3px] -z-10" />
          </div>
          <div className="flex items-baseline space-x-0.5">
            <span className="text-base font-extrabold tracking-tight text-[#FCF2E5]">
              Vibe
            </span>
            <span className="text-base font-black tracking-tight bg-gradient-to-r from-[#EC5B38] via-[#f79477] to-[#FCF2E5] bg-clip-text text-transparent">
              Study
            </span>
          </div>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center rounded-lg bg-[#1a1414] p-1 border border-[#524646]/80">
          <button
            onClick={() => setActiveTab('chat')}
            className={`flex items-center space-x-2 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              activeTab === 'chat'
                ? 'bg-[#EC5B38] text-[#FCF2E5] shadow-sm font-semibold'
                : 'text-[#A8A492] hover:text-[#FCF2E5] hover:bg-[#2b2323]'
            }`}
          >
            <MessageSquare className="h-3.5 w-3.5" />
            <span>Study Assistant</span>
          </button>
          <button
            onClick={() => {
              setActiveTab('corpus');
              fetchCorpus();
            }}
            className={`flex items-center space-x-2 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              activeTab === 'corpus'
                ? 'bg-[#EC5B38] text-[#FCF2E5] shadow-sm font-semibold'
                : 'text-[#A8A492] hover:text-[#FCF2E5] hover:bg-[#2b2323]'
            }`}
          >
            <Layers className="h-3.5 w-3.5" />
            <span>Course Corpus ({corpusStats.total_documents})</span>
          </button>
          <button
            onClick={() => setActiveTab('benchmark')}
            className={`flex items-center space-x-2 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              activeTab === 'benchmark'
                ? 'bg-[#EC5B38] text-[#FCF2E5] shadow-sm font-semibold'
                : 'text-[#A8A492] hover:text-[#FCF2E5] hover:bg-[#2b2323]'
            }`}
          >
            <BarChart2 className="h-3.5 w-3.5" />
            <span>Evaluation Benchmark</span>
          </button>
        </div>

        {/* Right spacer to keep tabs centered */}
        <div className="min-w-[130px] hidden sm:block" />
      </header>

      {/* Main Workspace Area */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* ===================== VIEW 1: CHAT & STUDY ASSISTANT ===================== */}
        {activeTab === 'chat' && (
          <div className="flex flex-1 h-full overflow-hidden">
            {/* Chat Stream Panel */}
            <div className={`flex flex-col h-full transition-all duration-300 ${inspectorOpen ? 'w-1/2 border-r border-[#524646]/70' : 'w-full'}`}>
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {messages.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                  >
                    <div className="flex items-center space-x-2 mb-1 text-[11px] font-mono text-[#A8A492]">
                      <span>{msg.role === 'user' ? 'STUDENT QUESTION' : 'GROUNDED ASSISTANT'}</span>
                    </div>

                    <div
                      className={`max-w-2xl rounded-xl p-4 text-sm leading-relaxed shadow-sm ${
                        msg.role === 'user'
                          ? 'bg-[#EC5B38] text-[#FCF2E5] font-medium rounded-tr-none shadow-md shadow-[#EC5B38]/15'
                          : msg.is_refusal
                          ? 'bg-[#381f1a]/90 text-[#fca995] border border-[#EC5B38]/50 rounded-tl-none'
                          : 'bg-[#251e1e] text-[#FCF2E5] border border-[#524646] rounded-tl-none'
                      }`}
                    >
                      {msg.is_refusal && (
                        <div className="flex items-center space-x-2 mb-2 pb-2 border-b border-[#EC5B38]/30 text-[#EC5B38] text-xs font-semibold tracking-wide">
                          <AlertTriangle className="h-3.5 w-3.5" />
                          <span>OUT-OF-CORPUS REFUSAL</span>
                        </div>
                      )}

                      <div className="whitespace-pre-wrap">{msg.content}</div>

                      {/* Source Citation Chips */}
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="mt-4 pt-3 border-t border-[#524646]/70">
                          <div className="text-[11px] font-semibold text-[#A8A492] mb-2 tracking-wider uppercase font-mono">
                            VERIFIED CITATIONS ({msg.sources.length})
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {msg.sources.map((src, sIdx) => (
                              <button
                                key={sIdx}
                                onClick={() => openSourceInspector(src)}
                                className="flex items-center space-x-1.5 rounded-md bg-[#342c2c] hover:bg-[#443838] border border-[#524646] hover:border-[#EC5B38]/80 px-2.5 py-1 text-xs text-[#FCF2E5] transition-colors group"
                              >
                                {src.ocr ? (
                                  <ImageIcon className="h-3 w-3 text-[#e8a34d]" />
                                ) : (
                                  <FileText className="h-3 w-3 text-[#EC5B38]" />
                                )}
                                <span className="font-mono font-medium">
                                  {src.filename} : Page {src.page}
                                </span>
                                {src.ocr && (
                                  <span className="text-[9px] px-1 py-0.2 rounded bg-[#524646] text-[#FCF2E5] font-mono border border-[#A8A492]/40">
                                    OCR
                                  </span>
                                )}
                                <ExternalLink className="h-2.5 w-2.5 opacity-60 group-hover:opacity-100" />
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {loading && (
                  <div className="flex items-start">
                    <div className="rounded-xl rounded-tl-none bg-[#251e1e] border border-[#524646] p-4 text-xs font-mono text-[#A8A492] flex items-center space-x-3">
                      <RefreshCw className="h-3.5 w-3.5 animate-spin text-[#EC5B38]" />
                      <span>Retrieving vectors & synthesizing grounded evidence...</span>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Chat Input Bar */}
              <div className="border-t border-[#524646]/70 bg-[#211a1a] p-4">
                <form onSubmit={handleSendQuery} className="flex items-center space-x-3">
                  <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Ask an exam question (e.g., 'What is the time complexity of binary search?')"
                    className="flex-1 rounded-lg border border-[#524646] bg-[#161212] px-4 py-2.5 text-sm text-[#FCF2E5] placeholder-[#A8A492]/60 focus:border-[#EC5B38] focus:outline-none focus:ring-1 focus:ring-[#EC5B38]"
                  />
                  <button
                    type="submit"
                    disabled={loading || !query.trim()}
                    className="flex items-center space-x-1.5 rounded-lg bg-[#EC5B38] hover:bg-[#ff714f] disabled:bg-[#342c2c] disabled:text-[#A8A492]/50 px-5 py-2.5 text-xs font-semibold text-[#FCF2E5] transition-colors"
                  >
                    <span>Send Query</span>
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </form>
                <div className="mt-2 flex items-center justify-between text-[11px] text-[#A8A492] font-mono">
                  <span>Grounding: Strict Course Scope</span>
                  <span>Parametric Hallucination: Disabled</span>
                </div>
              </div>
            </div>

            {/* Side-by-Side Page Inspector Panel */}
            {inspectorOpen && inspectingSource && (
              <div className="w-1/2 h-full flex flex-col bg-[#1a1414] overflow-hidden">
                {/* Inspector Header */}
                <div className="flex items-center justify-between border-b border-[#524646]/70 bg-[#241d1d] px-4 py-3">
                  <div className="flex items-center space-x-2">
                    <FileCheck className="h-4 w-4 text-[#EC5B38]" />
                    <div>
                      <span className="text-xs font-semibold text-[#FCF2E5]">
                        {inspectingSource.filename}
                      </span>
                      <span className="ml-2 text-xs font-mono text-[#EC5B38]">
                        Page {inspectingSource.page}
                      </span>
                      {inspectingSource.ocr && (
                        <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-[#524646] text-[#FCF2E5] font-mono border border-[#A8A492]/40">
                          HANDWRITTEN OCR
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Zoom Controls & Close */}
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => setZoomLevel((z) => Math.max(0.6, z - 0.2))}
                      className="p-1.5 rounded bg-[#342c2c] hover:bg-[#443838] text-[#FCF2E5] border border-[#524646]/60"
                      title="Zoom Out"
                    >
                      <ZoomOut className="h-3.5 w-3.5" />
                    </button>
                    <span className="text-xs font-mono text-[#A8A492] px-1">
                      {Math.round(zoomLevel * 100)}%
                    </span>
                    <button
                      onClick={() => setZoomLevel((z) => Math.min(2.5, z + 0.2))}
                      className="p-1.5 rounded bg-[#342c2c] hover:bg-[#443838] text-[#FCF2E5] border border-[#524646]/60"
                      title="Zoom In"
                    >
                      <ZoomIn className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => setZoomLevel(1.0)}
                      className="p-1.5 rounded bg-[#342c2c] hover:bg-[#443838] text-[#FCF2E5] border border-[#524646]/60"
                      title="Reset Zoom"
                    >
                      <RotateCcw className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => setInspectorOpen(false)}
                      className="p-1.5 rounded bg-[#342c2c] hover:bg-[#52231e] text-[#A8A492] hover:text-[#FCF2E5] border border-[#524646]/60"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>

                {/* Excerpt Snippet Highlight */}
                <div className="border-b border-[#524646]/70 bg-[#211a1a] p-3 text-xs text-[#A8A492] font-mono">
                  <div className="text-[10px] text-[#A8A492] mb-1 font-semibold uppercase">Retrieved Context Excerpt:</div>
                  <div className="bg-[#161111] p-2.5 rounded border border-[#524646]/60 whitespace-pre-wrap leading-relaxed text-[#FCF2E5]">
                    {inspectingSource.snippet}
                  </div>
                </div>

                {/* Rendered Document Page Scans */}
                <div className="flex-1 overflow-auto p-4 flex items-start justify-center bg-[#130f0f]">
                  {inspectingSource.image_url ? (
                    <div
                      style={{
                        transform: `scale(${zoomLevel})`,
                        transformOrigin: 'top center',
                        transition: 'transform 0.15s ease'
                      }}
                      className="max-w-full flex items-center justify-center my-auto transition-transform"
                    >
                      <img
                        src={inspectingSource.image_url}
                        alt={`Document page scan: ${inspectingSource.filename} page ${inspectingSource.page}`}
                        className="max-w-full max-h-[72vh] w-auto h-auto rounded-lg shadow-2xl border border-[#524646] bg-white object-contain"
                      />
                    </div>
                  ) : (
                    <div className="text-center p-8 text-[#A8A492] text-xs font-mono">
                      [Document page image preview unavailable for pure text/markdown source]
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ===================== VIEW 2: COURSE CORPUS MANAGER ===================== */}
        {activeTab === 'corpus' && (
          <div className="flex-1 flex flex-col p-8 overflow-y-auto bg-[#181414]">
            {/* Header & Stats Cards */}
            <div className="flex items-center justify-between mb-8">
              <div>
                <h1 className="text-xl font-bold text-[#FCF2E5]">Course Materials Corpus</h1>
                <p className="text-xs text-[#A8A492] mt-1">
                  Ingested slides, handbooks, markdown study notes, and handwritten exam sheets.
                </p>
              </div>
              <button
                onClick={() => setUploadModalOpen(true)}
                className="flex items-center space-x-2 rounded-lg bg-[#EC5B38] hover:bg-[#ff714f] px-4 py-2 text-xs font-semibold text-[#FCF2E5] transition-colors shadow-sm shadow-[#EC5B38]/20"
              >
                <Upload className="h-3.5 w-3.5" />
                <span>Upload Document</span>
              </button>
            </div>

            {/* KPI Cards */}
            <div className="grid grid-cols-4 gap-4 mb-8">
              <div className="rounded-xl border border-[#524646]/80 bg-[#251e1e] p-4 shadow-sm">
                <div className="text-xs font-mono text-[#A8A492]">TOTAL DOCUMENTS</div>
                <div className="text-2xl font-bold text-[#FCF2E5] mt-1">{corpusStats.total_documents}</div>
              </div>
              <div className="rounded-xl border border-[#524646]/80 bg-[#251e1e] p-4 shadow-sm">
                <div className="text-xs font-mono text-[#A8A492]">TOTAL INGESTED PAGES</div>
                <div className="text-2xl font-bold text-[#EC5B38] mt-1">{corpusStats.total_pages}</div>
              </div>
              <div className="rounded-xl border border-[#524646]/80 bg-[#251e1e] p-4 shadow-sm">
                <div className="text-xs font-mono text-[#A8A492]">INDEXED DENSE CHUNKS</div>
                <div className="text-2xl font-bold text-[#FCF2E5] mt-1">{corpusStats.total_chunks}</div>
              </div>
              <div className="rounded-xl border border-[#524646]/80 bg-[#251e1e] p-4 shadow-sm">
                <div className="text-xs font-mono text-[#A8A492]">VECTOR EMBEDDING DIM</div>
                <div className="text-2xl font-bold text-[#A8A492] mt-1">3072 (Gemini-v2)</div>
              </div>
            </div>

            {/* Search Bar */}
            <div className="flex items-center space-x-3 mb-6">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-[#A8A492]" />
                <input
                  type="text"
                  value={corpusSearch}
                  onChange={(e) => setCorpusSearch(e.target.value)}
                  placeholder="Filter documents by filename..."
                  className="w-full rounded-lg border border-[#524646] bg-[#221b1b] pl-9 pr-4 py-2 text-xs text-[#FCF2E5] placeholder-[#A8A492]/60 focus:border-[#EC5B38] focus:outline-none"
                />
              </div>
              <button
                onClick={fetchCorpus}
                className="p-2 rounded-lg bg-[#251e1e] border border-[#524646] text-[#A8A492] hover:text-[#FCF2E5]"
              >
                <RefreshCw className="h-4 w-4" />
              </button>
            </div>

            {/* Documents Table */}
            <div className="rounded-xl border border-[#524646]/80 bg-[#221b1b] overflow-hidden shadow-sm">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-[#524646] bg-[#2a2222] font-mono text-[#A8A492]">
                  <tr>
                    <th className="py-3.5 px-4">DOCUMENT FILENAME</th>
                    <th className="py-3.5 px-4">FORMAT</th>
                    <th className="py-3.5 px-4">PAGES</th>
                    <th className="py-3.5 px-4">CHUNKS</th>
                    <th className="py-3.5 px-4">OCR STATUS</th>
                    <th className="py-3.5 px-4">INGESTION STATUS</th>
                    <th className="py-3.5 px-4">INDEXED AT</th>
                    <th className="py-3.5 px-4 text-right">ACTION</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#524646]/60 font-mono">
                  {filteredDocs.map((doc) => (
                    <tr key={doc.doc_id} className="hover:bg-[#2e2626] transition-colors">
                      <td className="py-3.5 px-4 font-semibold text-[#FCF2E5] flex items-center space-x-2">
                        {doc.format === 'handwritten_scan' ? (
                          <ImageIcon className="h-4 w-4 text-[#e8a34d]" />
                        ) : (
                          <FileText className="h-4 w-4 text-[#EC5B38]" />
                        )}
                        <span>{doc.filename}</span>
                      </td>
                      <td className="py-3.5 px-4">
                        <span className="rounded bg-[#342c2c] px-2 py-0.5 text-[10px] text-[#A8A492] uppercase border border-[#524646]">
                          {doc.format}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-[#FCF2E5]">{doc.page_count}</td>
                      <td className="py-3.5 px-4 text-[#FCF2E5]">{doc.chunk_count}</td>
                      <td className="py-3.5 px-4">
                        {doc.ocr_pages > 0 ? (
                          <span className="rounded bg-[#3d2b27] text-[#ffb49e] px-2 py-0.5 text-[10px] border border-[#EC5B38]/40">
                            {doc.ocr_pages} pages VLM OCR
                          </span>
                        ) : (
                          <span className="text-[#A8A492] text-[11px]">Direct Text</span>
                        )}
                      </td>
                      <td className="py-3.5 px-4">
                        {doc.status === 'processing' ? (
                          <span className="flex items-center space-x-1.5 rounded bg-[#4a2e26] text-[#ffa38b] px-2 py-0.5 text-[10px] border border-[#EC5B38]/40 animate-pulse font-mono">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            <span>{doc.progress || 0}%</span>
                          </span>
                        ) : doc.status === 'failed' ? (
                          <span className="rounded bg-[#452220] text-[#fca995] px-2 py-0.5 text-[10px] border border-[#EC5B38]/40 font-mono">
                            FAILED
                          </span>
                        ) : (
                          <span className="flex items-center space-x-1 rounded bg-[#242b22] text-[#b5deb0] px-2 py-0.5 text-[10px] border border-[#7a9a70]/40 font-mono">
                            <CheckCircle2 className="h-3 w-3" />
                            <span>READY</span>
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-[#A8A492] text-[11px]">{doc.created_at}</td>
                      <td className="py-3.5 px-4 text-right">
                        <button
                          onClick={() => handleDeleteDocument(doc.doc_id, doc.filename)}
                          className="p-1.5 rounded bg-[#342c2c] hover:bg-[#52231e] text-[#A8A492] hover:text-[#FCF2E5] border border-[#524646] transition-colors"
                          title="Remove document from corpus"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>

              </table>
            </div>
          </div>
        )}

        {/* ===================== VIEW 3: BENCHMARK & EVALUATION ===================== */}
        {activeTab === 'benchmark' && (
          <div className="flex-1 flex flex-col p-8 overflow-y-auto bg-[#181414]">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
              <div>
                <h1 className="text-xl font-bold text-[#FCF2E5]">Evaluation Baseline Benchmark</h1>
                <p className="text-xs text-[#A8A492] mt-1">
                  Automated test suite against 20 target questions and 10 syllabus refusal queries. Target refusal rate: 100%.
                </p>
              </div>
              <button
                onClick={handleRunBenchmark}
                disabled={benchmarkLoading}
                className="flex items-center space-x-2 rounded-lg bg-[#EC5B38] hover:bg-[#ff714f] disabled:bg-[#342c2c] disabled:text-[#A8A492]/50 px-5 py-2.5 text-xs font-semibold text-[#FCF2E5] transition-colors shadow-sm shadow-[#EC5B38]/20"
              >
                {benchmarkLoading ? (
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <BarChart2 className="h-3.5 w-3.5" />
                )}
                <span>{benchmarkLoading ? 'Running Evaluation Suite...' : 'Run Benchmark (30 Tests)'}</span>
              </button>
            </div>

            {/* KPI Cards */}
            {benchmarkData && (
              <div className="grid grid-cols-4 gap-4 mb-8">
                <div className="rounded-xl border border-[#524646]/80 bg-[#251e1e] p-4 shadow-sm">
                  <div className="text-xs font-mono text-[#A8A492]">REFUSAL ACCURACY (10 TESTS)</div>
                  <div className={`text-2xl font-bold mt-1 ${benchmarkData.refusal_accuracy === 100 ? 'text-[#b5deb0]' : 'text-[#EC5B38]'}`}>
                    {benchmarkData.refusal_accuracy}%
                  </div>
                  <div className="text-[10px] text-[#A8A492] mt-1">Target Constraint: 100.0%</div>
                </div>
                <div className="rounded-xl border border-[#524646]/80 bg-[#251e1e] p-4 shadow-sm">
                  <div className="text-xs font-mono text-[#A8A492]">CITATION ACCURACY (20 TESTS)</div>
                  <div className="text-2xl font-bold text-[#EC5B38] mt-1">
                    {benchmarkData.citation_accuracy}%
                  </div>
                  <div className="text-[10px] text-[#A8A492] mt-1">Expected vs Retrieved Pages</div>
                </div>
                <div className="rounded-xl border border-[#524646]/80 bg-[#251e1e] p-4 shadow-sm">
                  <div className="text-xs font-mono text-[#A8A492]">OVERALL BENCHMARK PASS RATE</div>
                  <div className="text-2xl font-bold text-[#FCF2E5] mt-1">
                    {benchmarkData.overall_pass_rate}%
                  </div>
                  <div className="text-[10px] text-[#A8A492] mt-1">Groundedness & Keywords</div>
                </div>
                <div className="rounded-xl border border-[#524646]/80 bg-[#251e1e] p-4 shadow-sm">
                  <div className="text-xs font-mono text-[#A8A492]">EVALUATION RUN ID</div>
                  <div className="text-sm font-mono text-[#FCF2E5] mt-2 truncate">
                    {benchmarkData.run_id}
                  </div>
                  <div className="text-[10px] font-mono text-[#A8A492] mt-1">{benchmarkData.timestamp}</div>
                </div>
              </div>
            )}

            {/* Filter Tabs */}
            {benchmarkData && (
              <div className="flex items-center space-x-2 mb-4">
                <button
                  onClick={() => setBenchmarkFilter('all')}
                  className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-colors ${
                    benchmarkFilter === 'all' ? 'bg-[#EC5B38] text-[#FCF2E5]' : 'bg-[#2a2222] text-[#A8A492] hover:text-[#FCF2E5] border border-[#524646]/60'
                  }`}
                >
                  ALL ({benchmarkData.total_questions})
                </button>
                <button
                  onClick={() => setBenchmarkFilter('target')}
                  className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-colors ${
                    benchmarkFilter === 'target' ? 'bg-[#EC5B38] text-[#FCF2E5]' : 'bg-[#2a2222] text-[#A8A492] hover:text-[#FCF2E5] border border-[#524646]/60'
                  }`}
                >
                  TARGET QUESTIONS ({benchmarkData.target_questions})
                </button>
                <button
                  onClick={() => setBenchmarkFilter('refusal')}
                  className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-colors ${
                    benchmarkFilter === 'refusal' ? 'bg-[#EC5B38] text-[#FCF2E5]' : 'bg-[#2a2222] text-[#A8A492] hover:text-[#FCF2E5] border border-[#524646]/60'
                  }`}
                >
                  REFUSAL SET ({benchmarkData.refusal_questions})
                </button>
                <button
                  onClick={() => setBenchmarkFilter('failed')}
                  className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-colors ${
                    benchmarkFilter === 'failed' ? 'bg-[#c93f20] text-[#FCF2E5]' : 'bg-[#2a2222] text-[#A8A492] hover:text-[#FCF2E5] border border-[#524646]/60'
                  }`}
                >
                  FAILED TESTS
                </button>
              </div>
            )}

            {/* Benchmark Questions Table */}
            {benchmarkData ? (
              <div className="rounded-xl border border-[#524646]/80 bg-[#221b1b] overflow-hidden shadow-sm">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-[#524646] bg-[#2a2222] font-mono text-[#A8A492]">
                    <tr>
                      <th className="py-3 px-4">ID</th>
                      <th className="py-3 px-4">TYPE</th>
                      <th className="py-3 px-4">QUESTION</th>
                      <th className="py-3 px-4">STATUS</th>
                      <th className="py-3 px-4">REFUSAL</th>
                      <th className="py-3 px-4">CITATION</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#524646]/60 font-mono">
                    {filteredBenchmarkQuestions?.map((q) => (
                      <tr key={q.id} className="hover:bg-[#2e2626] transition-colors">
                        <td className="py-3 px-4 font-bold text-[#FCF2E5]">{q.id}</td>
                        <td className="py-3 px-4">
                          <span className="rounded bg-[#342c2c] px-1.5 py-0.5 text-[10px] text-[#A8A492] uppercase border border-[#524646]">
                            {q.type}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-sans text-[#FCF2E5] max-w-md truncate" title={q.question}>
                          {q.question}
                        </td>
                        <td className="py-3 px-4">
                          {q.passed ? (
                            <span className="flex items-center space-x-1 text-[#b5deb0]">
                              <CheckCircle2 className="h-3.5 w-3.5" />
                              <span>PASS</span>
                            </span>
                          ) : (
                            <span className="flex items-center space-x-1 text-[#ff8e75]">
                              <XCircle className="h-3.5 w-3.5" />
                              <span>FAIL</span>
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          {q.is_refusal ? (
                            <span className="text-[#EC5B38] font-semibold">REFUSED</span>
                          ) : (
                            <span className="text-[#A8A492]">ANSWERED</span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          {q.citation_correct ? (
                            <span className="text-[#b5deb0]">MATCH</span>
                          ) : (
                            <span className="text-[#ff8e75]">MISMATCH</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="rounded-xl border border-[#524646]/80 bg-[#221b1b] p-12 text-center text-[#A8A492] font-mono text-xs shadow-sm">
                Click "Run Benchmark" above to evaluate system groundedness, page citation accuracy, and 100% out-of-corpus refusal rate.
              </div>
            )}
          </div>
        )}
      </div>

      {/* Upload Document Modal */}
      {uploadModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-xl border border-[#524646] bg-[#231d1d] p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-[#FCF2E5]">Upload Course Material</h2>
              <button
                onClick={() => {
                  setUploadModalOpen(false);
                  setUploadMsg(null);
                }}
                className="text-[#A8A492] hover:text-[#FCF2E5]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleFileUpload} className="space-y-4">
              <div className="rounded-lg border border-dashed border-[#524646] bg-[#1a1414] p-6 text-center">
                <Upload className="mx-auto h-8 w-8 text-[#EC5B38] mb-2" />
                <p className="text-xs text-[#FCF2E5] font-medium">Select PDF, Slide Deck, Scan, or Markdown</p>
                <p className="text-[10px] text-[#A8A492] mt-1">Supported: .pdf, .png, .jpg, .md, .txt</p>
                <input
                  type="file"
                  disabled={uploading}
                  onChange={(e) => setUploadFile(e.target.files[0])}
                  className="mt-4 block w-full text-xs text-[#A8A492] file:mr-4 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-[#EC5B38] file:text-[#FCF2E5] hover:file:bg-[#ff714f] disabled:opacity-50"
                />
              </div>

              {/* Real-time Ingestion Progress Bar */}
              {uploadTask && (
                <div className="rounded-lg border border-[#524646] bg-[#161212] p-3.5 space-y-2.5">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-[#FCF2E5] font-semibold truncate max-w-[240px]">
                      {uploadTask.filename}
                    </span>
                    <span className="text-[#EC5B38] font-bold">{uploadTask.progress}%</span>
                  </div>

                  <div className="w-full bg-[#2a2222] rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-[#EC5B38] h-2 rounded-full transition-all duration-300 ease-out"
                      style={{ width: `${Math.max(5, uploadTask.progress)}%` }}
                    />
                  </div>

                  <div className="flex items-center space-x-2 text-[11px] text-[#A8A492] font-mono">
                    <Loader2 className="h-3 w-3 text-[#EC5B38] animate-spin shrink-0" />
                    <span className="truncate">{uploadTask.status_message || 'Processing document...'}</span>
                  </div>
                </div>
              )}

              {uploadMsg && (
                <div
                  className={`p-3 rounded text-xs font-mono flex items-center space-x-2 ${
                    uploadMsg.type === 'success'
                      ? 'bg-[#242b22] border border-[#7a9a70]/50 text-[#b5deb0]'
                      : 'bg-[#3d1f1a] border border-[#EC5B38]/50 text-[#fca995]'
                  }`}
                >
                  {uploadMsg.type === 'success' ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-[#b5deb0]" />
                  ) : (
                    <XCircle className="h-4 w-4 shrink-0 text-[#ff8e75]" />
                  )}
                  <span>{uploadMsg.text}</span>
                </div>
              )}

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  disabled={uploading}
                  onClick={() => {
                    setUploadModalOpen(false);
                    setUploadMsg(null);
                    setUploadTask(null);
                  }}
                  className="px-4 py-2 rounded-lg bg-[#342c2c] text-[#A8A492] text-xs font-medium hover:bg-[#443838] hover:text-[#FCF2E5] disabled:opacity-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!uploadFile || uploading}
                  className="flex items-center space-x-1.5 px-4 py-2 rounded-lg bg-[#EC5B38] hover:bg-[#ff714f] disabled:bg-[#342c2c] disabled:text-[#A8A492]/50 text-[#FCF2E5] text-xs font-semibold transition-colors shadow-sm shadow-[#EC5B38]/20"
                >
                  {uploading ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      <span>Processing ({uploadTask?.progress || 0}%)...</span>
                    </>
                  ) : (
                    <span>Ingest & Embed</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
