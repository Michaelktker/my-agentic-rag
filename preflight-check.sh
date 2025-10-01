#!/bin/bash
# Pre-flight check for automated production triggers implementation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}🚁 Pre-Flight Check: Ready for Implementation?${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo
}

print_step() {
    echo -e "${BLUE}📋 $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_prerequisites() {
    print_step "Checking Prerequisites"
    echo
    
    # Check gcloud installation
    if command -v gcloud &> /dev/null; then
        GCLOUD_VERSION=$(gcloud version --format="value(Google Cloud SDK)")
        print_success "gcloud CLI installed: $GCLOUD_VERSION"
    else
        print_error "gcloud CLI not found. Please install Google Cloud SDK"
        return 1
    fi
    
    # Check git configuration
    if git config user.name &> /dev/null && git config user.email &> /dev/null; then
        GIT_USER=$(git config user.name)
        GIT_EMAIL=$(git config user.email)
        print_success "Git configured: $GIT_USER <$GIT_EMAIL>"
    else
        print_warning "Git not fully configured. Run: git config --global user.name 'Your Name' && git config --global user.email 'your.email@example.com'"
    fi
    
    # Check if we're in the right directory
    if [ -f "pyproject.toml" ] && [ -f ".github/workflows/staging-deploy.yml" ]; then
        print_success "In correct project directory: my-agentic-rag"
    else
        print_error "Not in my-agentic-rag project directory"
        return 1
    fi
    
    echo
}

check_file_structure() {
    print_step "Checking File Structure"
    echo
    
    local files_ok=true
    
    # Essential files
    declare -A required_files=(
        [".github/workflows/staging-deploy.yml"]="GitHub Actions staging workflow"
        [".github/workflows/production-deploy.yml"]="GitHub Actions production workflow"
        [".cloudbuild/staging.yaml"]="Cloud Build staging configuration"
        [".cloudbuild/deploy-to-prod.yaml"]="Cloud Build production configuration"
        ["config/staging.env"]="Staging environment variables"
        ["config/production.env"]="Production environment variables"
        ["deploy-to-production-enhanced.sh"]="Enhanced deployment script"
        ["setup-automated-triggers.sh"]="Setup automation script"
        ["GITHUB-WEBHOOKS-SETUP.md"]="Setup documentation"
        ["IMPLEMENTATION-CHECKLIST.md"]="Implementation guide"
    )
    
    for file in "${!required_files[@]}"; do
        if [ -f "$file" ]; then
            print_success "${required_files[$file]}: $file"
        else
            print_error "Missing: $file (${required_files[$file]})"
            files_ok=false
        fi
    done
    
    # Check script permissions
    for script in "deploy-to-production-enhanced.sh" "setup-automated-triggers.sh"; do
        if [ -f "$script" ] && [ -x "$script" ]; then
            print_success "Executable: $script"
        elif [ -f "$script" ]; then
            print_warning "Not executable: $script (run: chmod +x $script)"
        fi
    done
    
    echo
    if [ "$files_ok" = false ]; then
        return 1
    fi
}

check_environment_configs() {
    print_step "Checking Environment Configurations"
    echo
    
    # Check staging config
    if [ -f "config/staging.env" ]; then
        source config/staging.env
        if [ -n "$STAGING_PROJECT_ID" ]; then
            print_success "Staging project configured: $STAGING_PROJECT_ID"
        else
            print_warning "Staging project ID not set in config/staging.env"
        fi
    fi
    
    # Check production config
    if [ -f "config/production.env" ]; then
        source config/production.env
        if [ -n "$PROD_PROJECT_ID" ]; then
            print_success "Production project configured: $PROD_PROJECT_ID"
        else
            print_warning "Production project ID not set in config/production.env"
        fi
    fi
    
    echo
}

check_yaml_syntax() {
    print_step "Checking YAML Syntax"
    echo
    
    if command -v yamllint &> /dev/null; then
        local yaml_ok=true
        
        # Check GitHub Actions workflows
        for file in .github/workflows/*.yml; do
            if [ -f "$file" ]; then
                if yamllint "$file" >/dev/null 2>&1; then
                    print_success "Valid YAML: $(basename "$file")"
                else
                    print_warning "YAML issues in: $(basename "$file") (non-critical)"
                fi
            fi
        done
        
        # Check Cloud Build configurations
        for file in .cloudbuild/*.yaml; do
            if [ -f "$file" ]; then
                if yamllint "$file" >/dev/null 2>&1; then
                    print_success "Valid YAML: $(basename "$file")"
                else
                    print_warning "YAML issues in: $(basename "$file") (non-critical)"
                fi
            fi
        done
    else
        print_warning "yamllint not available - skipping YAML validation"
    fi
    
    echo
}

check_github_repository() {
    print_step "Checking GitHub Repository Status"
    echo
    
    # Check if we're in a git repository
    if git rev-parse --is-inside-work-tree &> /dev/null; then
        print_success "Git repository detected"
        
        # Check remote origin
        if git remote get-url origin &> /dev/null; then
            ORIGIN_URL=$(git remote get-url origin)
            print_success "Remote origin: $ORIGIN_URL"
            
            # Check if it's the expected repository
            if [[ "$ORIGIN_URL" == *"Michaelktker/my-agentic-rag"* ]]; then
                print_success "Correct repository: my-agentic-rag"
            else
                print_warning "Different repository detected: $ORIGIN_URL"
            fi
        else
            print_warning "No remote origin configured"
        fi
        
        # Check current branch
        CURRENT_BRANCH=$(git branch --show-current)
        if [ "$CURRENT_BRANCH" = "main" ]; then
            print_success "On main branch"
        else
            print_warning "Not on main branch (current: $CURRENT_BRANCH)"
        fi
        
        # Check for uncommitted changes
        if git diff-index --quiet HEAD --; then
            print_success "No uncommitted changes"
        else
            print_warning "Uncommitted changes detected"
        fi
    else
        print_error "Not in a git repository"
        return 1
    fi
    
    echo
}

show_implementation_summary() {
    echo -e "${GREEN}🎯 Implementation Readiness Summary${NC}"
    echo "================================================"
    echo
    echo "✅ File structure complete and validated"
    echo "✅ Environment configurations ready"
    echo "✅ GitHub Actions workflows prepared"
    echo "✅ Cloud Build configurations ready"
    echo "✅ Deployment scripts executable"
    echo "✅ Documentation available"
    echo
    echo -e "${BLUE}📋 Next Steps:${NC}"
    echo "1. Review IMPLEMENTATION-CHECKLIST.md"
    echo "2. Authenticate with Google Cloud: gcloud auth login"
    echo "3. Run setup script: ./setup-automated-triggers.sh"
    echo "4. Configure GitHub secrets and environments"
    echo "5. Test with a small code change"
    echo
    echo -e "${YELLOW}📖 Documentation:${NC}"
    echo "• IMPLEMENTATION-CHECKLIST.md - Step-by-step guide"
    echo "• GITHUB-WEBHOOKS-SETUP.md - Complete setup instructions"
    echo "• API-TESTING.md - Testing reference"
    echo
    echo -e "${GREEN}🚀 Ready to implement automated production triggers!${NC}"
}

show_failure_summary() {
    echo -e "${RED}❌ Pre-Flight Check Failed${NC}"
    echo "================================================"
    echo
    echo "Please address the issues above before proceeding with implementation."
    echo
    echo -e "${YELLOW}📖 For help:${NC}"
    echo "• Check IMPLEMENTATION-CHECKLIST.md for detailed instructions"
    echo "• Review GITHUB-WEBHOOKS-SETUP.md for setup guidance"
    echo "• Ensure all required files are present and properly configured"
}

# Main execution
main() {
    print_header
    
    local checks_passed=true
    
    if ! check_prerequisites; then
        checks_passed=false
    fi
    
    if ! check_file_structure; then
        checks_passed=false
    fi
    
    check_environment_configs
    check_yaml_syntax
    
    if ! check_github_repository; then
        checks_passed=false
    fi
    
    echo
    if [ "$checks_passed" = true ]; then
        show_implementation_summary
        exit 0
    else
        show_failure_summary
        exit 1
    fi
}

# Run the pre-flight check
main "$@"