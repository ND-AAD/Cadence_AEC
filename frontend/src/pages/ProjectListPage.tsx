import { useState, useEffect, type FormEvent } from "react";
import { useNavigate, Link } from "react-router-dom";
import { listProjects, createProject, type ProjectItem } from "@/api/projects";

export default function ProjectListPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Inline creation state
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    loadProjects();
  }, []);

  async function loadProjects() {
    try {
      setLoading(true);
      const res = await listProjects();
      setProjects(res.items);
    } catch {
      setError("Failed to load projects");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setSubmitting(true);
    try {
      const project = await createProject({
        name: newName.trim(),
        description: newDesc.trim() || undefined,
      });
      navigate(`/project/${project.id}`);
    } catch {
      setError("Failed to create project");
      setSubmitting(false);
    }
  }

  function getDisplayName(p: ProjectItem): string {
    return p.identifier || (p.properties?.name as string) || "Untitled";
  }

  function getDescription(p: ProjectItem): string {
    return (p.properties?.description as string) || "";
  }

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-vellum flex items-center justify-center">
        <p className="text-sm text-trace">Loading projects…</p>
      </div>
    );
  }

  // Error state — API call failed, no cached projects to show
  if (error && projects.length === 0 && !creating) {
    return (
      <div className="min-h-screen bg-vellum flex flex-col items-center justify-center p-4">
        <p className="text-sm text-redline-ink mb-4">{error}</p>
        <button
          onClick={() => { setError(null); loadProjects(); }}
          className="px-4 py-2 text-sm font-medium bg-ink text-sheet hover:bg-ink/90 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  // Empty state — no projects, centered on vellum (DS-3 Screen 2, D7)
  if (projects.length === 0 && !creating) {
    return (
      <div className="min-h-screen bg-vellum flex flex-col items-center justify-center p-4">
        <h2 className="text-lg text-graphite mb-2">No projects yet</h2>
        <p className="text-sm text-trace mb-6 max-w-sm text-center">
          Create your first project to start tracking construction document changes.
        </p>
        <button
          onClick={() => setCreating(true)}
          className="px-4 py-2 text-sm font-medium bg-ink text-sheet hover:bg-ink/90 transition-colors"
        >
          Create Project
        </button>
      </div>
    );
  }

  // Empty state with inline form
  if (projects.length === 0 && creating) {
    return (
      <div className="min-h-screen bg-vellum flex flex-col items-center justify-center p-4">
        <div className="w-full max-w-sm bg-sheet border border-rule p-6">
          <h3 className="text-sm font-medium text-ink mb-4">New Project</h3>
          <form onSubmit={handleCreate} className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-graphite mb-1">
                Project Name
              </label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                required
                autoFocus
                placeholder="e.g. 200 Main Street"
                className="w-full px-3 py-2 text-sm bg-sheet border border-rule text-ink
                           focus:outline-none focus:border-ink transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-graphite mb-1">
                Description (optional)
              </label>
              <input
                type="text"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                placeholder="Brief project description"
                className="w-full px-3 py-2 text-sm bg-sheet border border-rule text-ink
                           focus:outline-none focus:border-ink transition-colors"
              />
            </div>
            {error && <p className="text-sm text-redline-ink">{error}</p>}
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => { setCreating(false); setNewName(""); setNewDesc(""); }}
                className="px-3 py-1.5 text-xs text-graphite border border-rule hover:text-ink transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || !newName.trim()}
                className="px-3 py-1.5 text-xs font-medium bg-ink text-sheet hover:bg-ink/90
                           transition-colors disabled:opacity-50"
              >
                {submitting ? "Creating…" : "Create"}
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  // With projects — breadcrumb bar + project cards (DS-3 Screen 2, D7)
  return (
    <div className="min-h-screen bg-vellum flex flex-col">
      {/* Breadcrumb bar */}
      <div className="h-10 bg-sheet border-b border-rule flex items-center px-4 shrink-0">
        <Link to="/projects" className="text-lg font-semibold tracking-tight text-ink select-none hover:text-ink/80 transition-colors">
          Cadence
        </Link>
      </div>

      {/* Project cards grid */}
      <div className="flex-1 overflow-auto p-6">
        {error && (
          <p className="text-sm text-redline-ink mb-4">{error}</p>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 max-w-5xl mx-auto">
          {projects.map((project) => (
            <button
              key={project.id}
              onClick={() => navigate(`/project/${project.id}`)}
              className="text-left bg-sheet border border-rule p-5 hover:border-ink/40
                         transition-colors group cursor-pointer"
            >
              <h3 className="text-lg font-semibold text-ink group-hover:text-ink/80 truncate">
                {getDisplayName(project)}
              </h3>
              {getDescription(project) && (
                <p className="text-sm text-graphite mt-1 line-clamp-2">
                  {getDescription(project)}
                </p>
              )}
              <p className="text-xs font-mono text-trace mt-3">
                {new Date(project.created_at).toLocaleDateString()}
              </p>
            </button>
          ))}

          {/* Dashed "+ Create Project" card */}
          {!creating ? (
            <button
              onClick={() => setCreating(true)}
              className="border border-dashed border-rule p-5 flex items-center justify-center
                         text-sm text-trace hover:text-graphite hover:border-ink/30
                         transition-colors cursor-pointer min-h-[120px]"
            >
              + Create Project
            </button>
          ) : (
            /* Inline creation form in place of the dashed card */
            <div className="bg-sheet border border-rule p-5">
              <h3 className="text-sm font-medium text-ink mb-3">New Project</h3>
              <form onSubmit={handleCreate} className="space-y-2">
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  required
                  autoFocus
                  placeholder="Project name"
                  className="w-full px-2 py-1.5 text-sm bg-sheet border border-rule text-ink
                             focus:outline-none focus:border-ink transition-colors"
                />
                <input
                  type="text"
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="Description (optional)"
                  className="w-full px-2 py-1.5 text-sm bg-sheet border border-rule text-ink
                             focus:outline-none focus:border-ink transition-colors"
                />
                <div className="flex justify-end gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => { setCreating(false); setNewName(""); setNewDesc(""); }}
                    className="px-2 py-1 text-xs text-graphite border border-rule hover:text-ink transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submitting || !newName.trim()}
                    className="px-2 py-1 text-xs font-medium bg-ink text-sheet hover:bg-ink/90
                               transition-colors disabled:opacity-50"
                  >
                    {submitting ? "Creating…" : "Create"}
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
