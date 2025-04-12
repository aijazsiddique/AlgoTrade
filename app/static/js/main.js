// Main JavaScript for AlgoTrade Platform

document.addEventListener('DOMContentLoaded', function() {
    // Sidebar toggling functionality has been removed
    
    // Enable tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Enable popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Auto-dismiss alerts
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        });
    }, 5000);
    
    // Activate submenu items based on current URL
    const currentPath = window.location.pathname;
    const submenuLinks = document.querySelectorAll('.sidebar-submenu .sidebar-link');
    
    submenuLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
            // Open parent submenu
            const parentCollapse = link.closest('.collapse');
            if (parentCollapse) {
                parentCollapse.classList.add('show');
                const parentTrigger = document.querySelector(`[data-bs-toggle="collapse"][href="#${parentCollapse.id}"]`);
                if (parentTrigger) {
                    parentTrigger.classList.remove('collapsed');
                }
            }
        }
    });
    
    // Strategy Testing
    const testStrategyButton = document.getElementById('test-strategy-button');
    if (testStrategyButton) {
        testStrategyButton.addEventListener('click', function() {
            const strategyId = this.dataset.strategyId;
            const symbolInput = document.getElementById('test-symbol');
            const exchangeInput = document.getElementById('test-exchange');
            const timeframeInput = document.getElementById('test-timeframe');
            
            const testResultsContainer = document.getElementById('test-results-container');
            const testLoadingSpinner = document.getElementById('test-loading-spinner');
            
            // Show loading spinner
            testLoadingSpinner.classList.remove('d-none');
            testResultsContainer.innerHTML = '';
            
            // Collect parameters
            const paramInputs = document.querySelectorAll('input[name^="param_"]');
            const params = {};
            
            paramInputs.forEach(function(input) {
                const paramName = input.name.replace('param_', '');
                let paramValue = input.value;
                
                // Convert to appropriate type
                if (input.type === 'number') {
                    paramValue = input.value.includes('.') ? parseFloat(input.value) : parseInt(input.value);
                } else if (input.type === 'checkbox') {
                    paramValue = input.checked;
                }
                
                params[paramName] = paramValue;
            });
            
            // Send test request
            fetch(`/strategies/${strategyId}/test`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    symbol: symbolInput.value,
                    exchange: exchangeInput.value,
                    timeframe: timeframeInput.value,
                    params: params
                })
            })
            .then(response => response.json())
            .then(data => {
                // Hide loading spinner
                testLoadingSpinner.classList.add('d-none');
                
                if (data.success) {
                    // Display results
                    let resultsHtml = '<div class="alert alert-success">';
                    resultsHtml += `<h5><i class="fas fa-check-circle"></i> Strategy Test Successful!</h5>`;
                    resultsHtml += `<p>${data.signals.length} signals generated.</p>`;
                    
                    if (data.signals.length > 0) {
                        resultsHtml += '<h6>Signals:</h6>';
                        resultsHtml += '<ul>';
                        data.signals.forEach((signal, index) => {
                            const signalType = signal[0];
                            const signalClass = signalType.includes('long') ? 'text-success' : 'text-danger';
                            const signalIcon = signalType.includes('entry') ? 'arrow-right' : 'sign-out-alt';
                            
                            resultsHtml += `<li class="${signalClass}"><i class="fas fa-${signalIcon}"></i> Signal #${index + 1}: ${signalType}</li>`;
                        });
                        resultsHtml += '</ul>';
                    }
                    
                    resultsHtml += '</div>';
                    testResultsContainer.innerHTML = resultsHtml;
                } else {
                    // Display error
                    testResultsContainer.innerHTML = `
                        <div class="alert alert-danger">
                            <h5><i class="fas fa-exclamation-triangle"></i> Strategy Test Failed!</h5>
                            <p>${data.error}</p>
                        </div>
                    `;
                }
            })
            .catch(error => {
                // Hide loading spinner and show error
                testLoadingSpinner.classList.add('d-none');
                testResultsContainer.innerHTML = `
                    <div class="alert alert-danger">
                        <h5><i class="fas fa-exclamation-triangle"></i> Error!</h5>
                        <p>Could not complete the test. Please try again.</p>
                        <p class="text-monospace small">${error}</p>
                    </div>
                `;
                console.error('Error testing strategy:', error);
            });
        });
    }
});
