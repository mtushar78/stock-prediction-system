'use client';

/**
 * TutorialModal — opens the pattern tutorial as an overlay, scrolled to a
 * specific pattern. Used to link a chart's reading (a scanner row or a modal
 * card) straight to the lesson for that exact pattern.
 */

import { useEffect, useState } from 'react';
import TutorialView from './TutorialView';
import { tutorialCodeFor, TUTORIALS } from '../tutorials';
import { X, GraduationCap } from 'lucide-react';

export default function TutorialModal({ code, onClose }: { code: string; onClose: () => void }) {
  const [active, setActive] = useState(() => tutorialCodeFor(code));

  useEffect(() => {
    setActive(tutorialCodeFor(code));
  }, [code]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  if (!TUTORIALS[active]) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/75 p-2" onClick={onClose}>
      <div
        className="bg-gray-900 rounded-lg shadow-2xl border border-purple-800/50 w-full max-w-[1100px] max-h-[95vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-4 border-b border-gray-700 flex items-center justify-between sticky top-0 bg-gray-900 z-10">
          <h2 className="text-lg font-bold text-purple-300 flex items-center gap-2">
            <GraduationCap className="w-5 h-5" /> Chart-Pattern Tutorial
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-6 h-6" />
          </button>
        </div>
        <div className="p-4">
          <TutorialView activeCode={active} onSelect={setActive} />
        </div>
      </div>
    </div>
  );
}
