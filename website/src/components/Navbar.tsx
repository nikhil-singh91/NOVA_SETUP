import React, { useState, useEffect } from 'react';
import { Menu, X, Github, Play } from 'lucide-react';

interface NavbarProps {
  onWatchDemo: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onWatchDemo }) => {
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 30);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const navLinks = [
    { name: 'Overview', href: '#overview' },
    { name: 'Capabilities', href: '#capabilities' },
    { name: 'NOVA × Anakin', href: '#anakin' },
    { name: 'Architecture', href: '#architecture' },
    { name: 'Workflow', href: '#workflow' },
    { name: 'Demo', href: '#demo' },
  ];

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-40 transition-all duration-300 ${
        scrolled
          ? 'py-3 bg-[#07090e]/85 backdrop-blur-xl border-b border-white/10 shadow-lg shadow-black/40'
          : 'py-5 bg-transparent'
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between">
        {/* Brand Logo */}
        <a href="#" className="flex items-center gap-3 group">
          <div className="relative w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-600/20 border border-cyan-500/30 flex items-center justify-center group-hover:border-cyan-400 transition-colors">
            <span className="font-mono font-black text-cyan-400 text-lg tracking-tighter">N</span>
            <div className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="font-extrabold tracking-tight text-white text-lg group-hover:text-cyan-300 transition-colors">
                NOVA
              </span>
              <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                v5
              </span>
            </div>
            <span className="text-[10px] font-mono text-slate-400 -mt-0.5 hidden sm:block">
              Anakin Forge 2026
            </span>
          </div>
        </a>

        {/* Desktop Nav Links */}
        <nav className="hidden md:flex items-center gap-1 px-4 py-1.5 rounded-full bg-white/[0.03] border border-white/10 backdrop-blur-md">
          {navLinks.map((link) => (
            <a
              key={link.name}
              href={link.href}
              className="px-3.5 py-1.5 text-xs font-medium text-slate-300 hover:text-white hover:bg-white/[0.06] rounded-full transition-colors"
            >
              {link.name}
            </a>
          ))}
        </nav>

        {/* Action Buttons */}
        <div className="hidden sm:flex items-center gap-3">
          <a
            href="https://github.com/nikhil-singh91/NOVA_SETUP"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 px-3.5 py-1.5 text-xs font-medium text-slate-300 hover:text-white bg-white/[0.05] hover:bg-white/[0.1] border border-white/10 rounded-lg transition-all"
          >
            <Github className="w-3.5 h-3.5" />
            <span>GitHub</span>
          </a>

          <button
            onClick={onWatchDemo}
            className="inline-flex items-center gap-2 px-4 py-1.5 text-xs font-semibold text-black bg-gradient-to-r from-cyan-400 to-sky-400 hover:from-cyan-300 hover:to-sky-300 rounded-lg shadow-md shadow-cyan-500/20 transition-all transform hover:-translate-y-0.5"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>Watch Demo</span>
          </button>
        </div>

        {/* Mobile Menu Button */}
        <div className="flex md:hidden items-center gap-2">
          <button
            onClick={onWatchDemo}
            className="p-2 text-cyan-400 hover:text-cyan-300"
            aria-label="Watch demo"
          >
            <Play className="w-4 h-4 fill-current" />
          </button>
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 text-slate-300 hover:text-white rounded-lg bg-white/5 border border-white/10"
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Menu Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden mt-3 px-4 pt-3 pb-6 bg-[#0c0f17]/95 border-b border-white/10 backdrop-blur-2xl animate-fade-in">
          <nav className="flex flex-col space-y-2">
            {navLinks.map((link) => (
              <a
                key={link.name}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
              >
                {link.name}
              </a>
            ))}
            <div className="pt-4 mt-2 border-t border-white/10 flex flex-col gap-2">
              <a
                href="https://github.com/nikhil-singh91/NOVA_SETUP"
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-medium text-white bg-white/5 border border-white/10 rounded-lg"
              >
                <Github className="w-4 h-4" />
                <span>View Source on GitHub</span>
              </a>
              <button
                onClick={() => {
                  setMobileMenuOpen(false);
                  onWatchDemo();
                }}
                className="flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-semibold text-black bg-cyan-400 hover:bg-cyan-300 rounded-lg shadow-lg shadow-cyan-500/20"
              >
                <Play className="w-4 h-4 fill-current" />
                <span>Watch NOVA in Action</span>
              </button>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
};
