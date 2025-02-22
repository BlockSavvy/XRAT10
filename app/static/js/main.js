// Form validation
(function () {
    'use strict'
    var forms = document.querySelectorAll('.needs-validation')
    Array.prototype.slice.call(forms)
        .forEach(function (form) {
            form.addEventListener('submit', function (event) {
                if (!form.checkValidity()) {
                    event.preventDefault()
                    event.stopPropagation()
                }
                form.classList.add('was-validated')
            }, false)
        })
})();

// Initialize DataTables
function initializeDataTable(tableId) {
    if (document.getElementById(tableId)) {
        $(tableId).DataTable({
            order: [[0, 'desc']],
            pageLength: 10,
            lengthMenu: [[10, 25, 50, -1], [10, 25, 50, "All"]],
            responsive: true
        });
    }
}

// Export to CSV
function exportToCSV(data, filename) {
    let csvContent = "data:text/csv;charset=utf-8,";
    csvContent += Object.keys(data[0]).join(",") + "\n";
    
    data.forEach(function(item) {
        let row = Object.values(item).join(",");
        csvContent += row + "\n";
    });
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Initialize Charts
function initializeSentimentChart(ctx, data) {
    if (!ctx) return;
    
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Positive', 'Negative', 'Neutral'],
            datasets: [{
                data: [data.positive, data.negative, data.neutral],
                backgroundColor: ['#28a745', '#dc3545', '#6c757d']
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function initializeTimelineChart(ctx, data) {
    if (!ctx) return;
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => new Date(d.timestamp).toLocaleTimeString()),
            datasets: [{
                label: 'Sentiment Score',
                data: data.map(d => d.compound_score),
                borderColor: '#1DA1F2',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

// Handle modal details
function loadAnalysisDetails(analysisId) {
    // Here you would typically make an AJAX call to get detailed analysis data
    $('#analysisDetails').html(`
        <div class="alert alert-info">
            Loading details for analysis #${analysisId}...
        </div>
    `);
} 