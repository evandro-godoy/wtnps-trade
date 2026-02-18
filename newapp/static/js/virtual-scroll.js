/**
 * VirtualScroll - Lightweight virtual scrolling for large tables
 * Renders only visible rows + buffer to maintain performance
 * 
 * Usage:
 *   const vs = new VirtualScroll(containerEl, 30);  // 30px row height
 *   vs.setData(largeArray);
 */

class VirtualScroll {
  constructor(container, rowHeight = 30, bufferSize = 5) {
    this.container = container;
    this.rowHeight = rowHeight;
    this.bufferSize = bufferSize;
    this.data = [];
    this.scrollTop = 0;
    this.visibleRange = { start: 0, end: 0 };
    
    // Find tbody or create wrapper
    this.tbody = container.querySelector('tbody');
    if (!this.tbody) {
      throw new Error('Virtual scroll requires <tbody> element');
    }
    
    // Create phantom elements for virtual scroll height
    this.topSpacer = document.createElement('tr');
    this.topSpacer.className = 'virtual-scroll-spacer';
    this.topSpacer.style.height = '0px';
    
    this.bottomSpacer = document.createElement('tr');
    this.bottomSpacer.className = 'virtual-scroll-spacer';
    this.bottomSpacer.style.height = '0px';
    
    // Append spacers
    this.tbody.appendChild(this.topSpacer);
    this.tbody.appendChild(this.bottomSpacer);
    
    // Bind scroll event to container (parent with overflow-y)
    const scrollContainer = this.getScrollContainer();
    if (scrollContainer) {
      scrollContainer.addEventListener('scroll', () => this.onScroll(), { passive: true });
    }
  }
  
  /**
   * Find the actual scrollable container
   * Usually .predictions-table-container or similar
   */
  getScrollContainer() {
    let parent = this.container.parentElement;
    while (parent) {
      const style = window.getComputedStyle(parent);
      if (style.overflowY === 'auto' || style.overflowY === 'scroll') {
        return parent;
      }
      parent = parent.parentElement;
    }
    return null;
  }
  
  /**
   * Set data and trigger initial render
   */
  setData(data) {
    this.data = data || [];
    this.scrollTop = 0;
    this.render();
  }
  
  /**
   * Calculate visible range based on scroll position
   */
  calculateVisibleRange() {
    const scrollContainer = this.getScrollContainer();
    if (!scrollContainer) {
      this.visibleRange = { start: 0, end: Math.min(50, this.data.length) };
      return;
    }
    
    const scrollTop = scrollContainer.scrollTop;
    const containerHeight = scrollContainer.clientHeight;
    
    // Calculate which rows should be visible
    const startRow = Math.max(0, Math.floor(scrollTop / this.rowHeight) - this.bufferSize);
    const visibleRows = Math.ceil(containerHeight / this.rowHeight) + this.bufferSize * 2;
    const endRow = Math.min(this.data.length, startRow + visibleRows);
    
    this.visibleRange = { start: startRow, end: endRow };
  }
  
  /**
   * Render only visible rows
   */
  render() {
    this.calculateVisibleRange();
    const { start, end } = this.visibleRange;
    
    // Update spacer heights
    const topHeight = start * this.rowHeight;
    const bottomHeight = Math.max(0, (this.data.length - end) * this.rowHeight);
    
    this.topSpacer.style.height = `${topHeight}px`;
    this.bottomSpacer.style.height = `${bottomHeight}px`;
    
    // Remove old rows (keep spacers)
    const oldRows = this.tbody.querySelectorAll('tr:not(.virtual-scroll-spacer)');
    oldRows.forEach(row => row.remove());
    
    // Render visible rows
    for (let i = start; i < end; i++) {
      const rowElement = this.createRowElement(this.data[i], i);
      this.tbody.insertBefore(rowElement, this.bottomSpacer);
    }
    
    console.log(`📊 VirtualScroll: Rendering rows ${start}-${end} of ${this.data.length}`);
  }
  
  /**
   * Hook for subclass to create row element
   * Override in subclass or pass as callback
   */
  createRowElement(rowData, index) {
    // Default: expects rowElement to be pre-created
    // This should be overridden or data should contain element
    if (rowData && rowData.element) {
      return rowData.element.cloneNode(true);
    }
    
    // Fallback: create empty row
    const row = document.createElement('tr');
    row.textContent = `Row ${index}`;
    return row;
  }
  
  /**
   * Handle scroll event
   */
  onScroll() {
    this.render();
  }
  
  /**
   * Update row height (useful if rows change size dynamically)
   */
  setRowHeight(height) {
    this.rowHeight = height;
    this.render();
  }
  
  /**
   * Scroll to specific row
   */
  scrollToRow(rowIndex) {
    const scrollContainer = this.getScrollContainer();
    if (!scrollContainer) return;
    
    scrollContainer.scrollTop = rowIndex * this.rowHeight;
  }
  
  /**
   * Get current visible range
   */
  getVisibleRange() {
    return { ...this.visibleRange };
  }
}

/**
 * Specialized version for prediction tables
 * Manages row creation from prediction objects
 */
class PredictionVirtualScroll extends VirtualScroll {
  constructor(tableContainer, rowHeight = 30, bufferSize = 5) {
    super(tableContainer, rowHeight, bufferSize);
    this.rowFactory = null;  // Function to create row elements
  }
  
  /**
   * Set the factory function for creating rows
   * factory(data, index) => HTMLTableRowElement
   */
  setRowFactory(factory) {
    this.rowFactory = factory;
  }
  
  /**
   * Override to use custom row factory
   */
  createRowElement(rowData, index) {
    if (this.rowFactory) {
      return this.rowFactory(rowData, index);
    }
    return super.createRowElement(rowData, index);
  }
}

// Export for use in HTML
window.VirtualScroll = VirtualScroll;
window.PredictionVirtualScroll = PredictionVirtualScroll;
