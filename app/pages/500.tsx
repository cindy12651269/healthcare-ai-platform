import ErrorPage from "../components/ErrorPage";

export default function ServerError() {
  return <ErrorPage code="500" title="Server error" message="The page could not be rendered. Try again shortly or return to the dashboard." />;
}
