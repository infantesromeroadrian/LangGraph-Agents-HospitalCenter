/**
 * LangGraph Medical Center - Graph Visualization with D3.js
 */

let graphData = null;
let simulation = null;
let svg = null;
let g = null;

/**
 * Initialize D3.js graph visualization
 */
function initializeGraph() {
    const container = document.getElementById('graph-container');
    
    if (!container) return;
    
    // Clear existing
    container.innerHTML = '';
    
    // Setup SVG
    const width = container.clientWidth;
    const height = container.clientHeight;
    
    svg = d3.select('#graph-container')
        .append('svg')
        .attr('width', width)
        .attr('height', height);
    
    // Add zoom capabilities
    const zoom = d3.zoom()
        .scaleExtent([0.5, 3])
        .on('zoom', function(event) {
            g.attr('transform', event.transform);
        });
    
    svg.call(zoom);
    
    // Group for zoomable content
    g = svg.append('g');
    
    // Initialize graph data
    graphData = {
        nodes: [],
        links: []
    };
    
    console.log('📊 Graph visualization initialized');
}

/**
 * Update graph with state information
 */
function updateGraph(stateData) {
    if (!svg || !g) {
        initializeGraph();
    }
    
    console.log('🔄 Updating graph with state:', stateData);
    
    // Build graph from state
    const nodes = buildNodesFromState(stateData);
    const links = buildLinksFromState(stateData);
    
    graphData = { nodes, links };
    
    // Render
    renderGraph();
}

/**
 * Build nodes from state
 */
function buildNodesFromState(stateData) {
    const nodes = [
        { id: 'update_context', label: 'Update Context', type: 'system' },
        { id: 'triage', label: 'Triage Agent', type: 'triage' },
    ];
    
    // Specialist nodes
    const specialties = [
        'general_medicine',
        'cardiology',
        'neurology',
        'pediatrics',
        'dermatology',
        'orthopedics',
        'psychiatry',
        'oncology'
    ];
    
    specialties.forEach(specialty => {
        nodes.push({
            id: `specialist_${specialty}`,
            label: getSpecialistDisplayName(specialty),
            type: 'specialist',
            specialty: specialty
        });
    });
    
    // Consensus node
    nodes.push({ id: 'consensus', label: 'Consensus Agent', type: 'consensus' });
    
    // Final response node
    nodes.push({ id: 'final_response', label: 'Final Response', type: 'system' });
    
    // Mark active node
    if (stateData && stateData.active_agent) {
        const activeId = stateData.active_agent.toLowerCase().replace(/\s+/g, '_');
        const activeNode = nodes.find(n => n.id.includes(activeId));
        
        if (activeNode) {
            activeNode.active = true;
        }
    }
    
    return nodes;
}

/**
 * Build links from state
 */
function buildLinksFromState(stateData) {
    const links = [];
    
    // Update Context -> Triage
    links.push({ source: 'update_context', target: 'triage', type: 'flow' });
    
    // Triage -> All Specialists (parallel)
    const specialties = [
        'general_medicine',
        'cardiology',
        'neurology',
        'pediatrics',
        'dermatology',
        'orthopedics',
        'psychiatry',
        'oncology'
    ];
    
    specialties.forEach(specialty => {
        links.push({
            source: 'triage',
            target: `specialist_${specialty}`,
            type: 'parallel'
        });
    });
    
    // All Specialists -> Consensus (join)
    specialties.forEach(specialty => {
        links.push({
            source: `specialist_${specialty}`,
            target: 'consensus',
            type: 'join'
        });
    });
    
    // Consensus -> Final Response
    links.push({ source: 'consensus', target: 'final_response', type: 'flow' });
    
    return links;
}

/**
 * Render the graph
 */
function renderGraph() {
    if (!graphData || !g) return;
    
    // Clear previous
    g.selectAll('*').remove();
    
    // Create force simulation
    const width = svg.attr('width');
    const height = svg.attr('height');
    
    simulation = d3.forceSimulation(graphData.nodes)
        .force('link', d3.forceLink(graphData.links)
            .id(d => d.id)
            .distance(150))
        .force('charge', d3.forceManyBody().strength(-400))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collide', d3.forceCollide().radius(50));
    
    // Draw links
    const link = g.append('g')
        .attr('class', 'links')
        .selectAll('line')
        .data(graphData.links)
        .enter()
        .append('line')
        .attr('class', d => `link link-${d.type}`)
        .attr('stroke', d => getLinkColor(d.type))
        .attr('stroke-width', 2)
        .attr('stroke-dasharray', d => d.type === 'parallel' ? '5,5' : null);
    
    // Draw nodes
    const node = g.append('g')
        .attr('class', 'nodes')
        .selectAll('g')
        .data(graphData.nodes)
        .enter()
        .append('g')
        .attr('class', d => `node node-${d.type} ${d.active ? 'active' : ''}`)
        .call(d3.drag()
            .on('start', dragstarted)
            .on('drag', dragged)
            .on('end', dragended));
    
    // Node circles
    node.append('circle')
        .attr('r', d => d.type === 'specialist' ? 40 : 35)
        .attr('fill', d => getNodeColor(d))
        .attr('stroke', d => d.active ? '#FFD700' : '#fff')
        .attr('stroke-width', d => d.active ? 4 : 2);
    
    // Node icons
    node.append('text')
        .attr('class', 'node-icon')
        .attr('text-anchor', 'middle')
        .attr('dy', '.35em')
        .attr('font-family', 'FontAwesome')
        .attr('font-size', '20px')
        .attr('fill', '#fff')
        .text(d => getNodeIcon(d));
    
    // Node labels
    node.append('text')
        .attr('class', 'node-label')
        .attr('text-anchor', 'middle')
        .attr('dy', '3em')
        .attr('font-size', '12px')
        .attr('font-weight', 'bold')
        .text(d => d.label);
    
    // Update positions on tick
    simulation.on('tick', () => {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
        
        node
            .attr('transform', d => `translate(${d.x},${d.y})`);
    });
}

/**
 * Get node color based on type
 */
function getNodeColor(node) {
    if (node.active) {
        return '#FFD700'; // Gold for active
    }
    
    switch (node.type) {
        case 'triage':
            return '#17a2b8'; // Info blue
        case 'specialist':
            return getSpecialistColor(node.specialty);
        case 'consensus':
            return '#6f42c1'; // Purple
        case 'system':
            return '#6c757d'; // Gray
        default:
            return '#007bff'; // Default blue
    }
}

/**
 * Get link color based on type
 */
function getLinkColor(type) {
    switch (type) {
        case 'parallel':
            return '#ffc107'; // Amber for parallel
        case 'join':
            return '#28a745'; // Green for join
        case 'flow':
        default:
            return '#6c757d'; // Gray for normal flow
    }
}

/**
 * Get node icon (Font Awesome unicode)
 */
function getNodeIcon(node) {
    switch (node.type) {
        case 'triage':
            return '\uf0f1'; // fa-stethoscope
        case 'specialist':
            return '\uf0f0'; // fa-user-md
        case 'consensus':
            return '\uf0c0'; // fa-users
        case 'system':
            return '\uf013'; // fa-cog
        default:
            return '\uf21e'; // fa-heartbeat
    }
}

/**
 * Drag functions
 */
function dragstarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
}

function dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
}

function dragended(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
}

/**
 * Highlight active node
 */
function highlightActiveNode(agentName) {
    if (!graphData) return;
    
    // Reset all nodes
    graphData.nodes.forEach(node => {
        node.active = false;
    });
    
    // Mark active node
    const activeId = agentName.toLowerCase().replace(/\s+/g, '_');
    const activeNode = graphData.nodes.find(n => n.id.includes(activeId));
    
    if (activeNode) {
        activeNode.active = true;
    }
    
    // Re-render
    renderGraph();
}

/**
 * Reset graph
 */
function resetGraph() {
    if (simulation) {
        simulation.stop();
    }
    
    graphData = null;
    
    if (g) {
        g.selectAll('*').remove();
    }
}

// Handle window resize
window.addEventListener('resize', () => {
    if (svg && graphData) {
        const container = document.getElementById('graph-container');
        
        if (container) {
            const width = container.clientWidth;
            const height = container.clientHeight;
            
            svg.attr('width', width).attr('height', height);
            
            if (simulation) {
                simulation.force('center', d3.forceCenter(width / 2, height / 2));
                simulation.alpha(0.3).restart();
            }
        }
    }
});

