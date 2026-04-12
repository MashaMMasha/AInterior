import React, { useState, useCallback, useEffect } from 'react';
import './ResizablePanel.css';

const ResizablePanel = ({ 
  children, 
  side = 'left', 
  minWidth = 250, 
  maxWidth = 600, 
  defaultWidth = 350,
  collapsed = false,
  onToggle
}) => {
  const [width, setWidth] = useState(defaultWidth);
  const [isResizing, setIsResizing] = useState(false);

  useEffect(() => {
    const handler = (event) => {
      const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
      const modifierKey = isMac ? event.metaKey : event.ctrlKey;
      
      // Cmd/Ctrl + B для левой панели
      if (side === 'left' && modifierKey && event.key === 'b') {
        event.preventDefault();
        onToggle?.();
      }
      
      // Cmd/Ctrl + \ для правой панели
      if (side === 'right' && modifierKey && event.key === '\\') {
        event.preventDefault();
        onToggle?.();
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [side, onToggle]);

  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    setIsResizing(true);

    const startX = e.clientX;
    const startWidth = width;

    const handleMouseMove = (e) => {
      const delta = side === 'left' ? e.clientX - startX : startX - e.clientX;
      const newWidth = Math.min(Math.max(startWidth + delta, minWidth), maxWidth);
      setWidth(newWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [width, side, minWidth, maxWidth]);

  return (
    <div 
      className={`resizable-panel ${side} ${collapsed ? 'collapsed' : ''}`} 
      style={{ width: collapsed ? '0px' : `${width}px` }}
    >
      {children}
      {!collapsed && (
        <div 
          className={`resize-handle ${side} ${isResizing ? 'resizing' : ''}`}
          onMouseDown={handleMouseDown}
        >
          <div className="resize-handle-line" />
        </div>
      )}
    </div>
  );
};

export default ResizablePanel;
